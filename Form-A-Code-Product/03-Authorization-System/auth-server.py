#!/usr/bin/env python3
"""
Form-A 授权验证服务 (auth-server)
==================================
License 管理与验证的核心服务，基于 Flask + SQLite + RSA 非对称签名。

功能:
  - RSA 密钥对自动生成与管理
  - License 签发（签名 + 编码）
  - License 验证（验签 + 过期 + 机器指纹）
  - 首次激活（机器绑定）
  - 续期
  - 分销商追踪
  - 管理员查询

运行: python auth-server.py
默认监听: http://0.0.0.0:5000
"""

import datetime
import hashlib
import hmac
import json
import os
import platform
import sqlite3
import subprocess
import sys
import time
import uuid
from base64 import b64decode, b64encode
from functools import wraps
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.backends import default_backend
from flask import Flask, g, jsonify, request

# ──────────────────────────── 配置 ────────────────────────────

class Config:
    """应用配置，支持环境变量覆盖"""
    DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "data", "auth.db"))
    PRIVATE_KEY_PATH = os.environ.get("PRIVATE_KEY_PATH", os.path.join(os.path.dirname(__file__), "data", "private.pem"))
    PUBLIC_KEY_PATH = os.environ.get("PUBLIC_KEY_PATH", os.path.join(os.path.dirname(__file__), "data", "public.pem"))
    SECRET_KEY = os.environ.get("SECRET_KEY", hashlib.sha256(os.urandom(64)).hexdigest())
    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = int(os.environ.get("PORT", 5000))
    OFFLINE_CACHE_DAYS = 7
    MAX_FINGERPRINT_MISMATCH = 1  # 4个指纹中最多允许1个不匹配
    LICENSE_CHECK_INTERVAL_DAYS = 7  # 联网校验间隔

    # 版本功能边界
    EDITION_FEATURES = {
        "community": {
            "max_workflows": 10,
            "max_users": 5,
            "ai_calls_per_day": 100,
            "data_retention_days": 30,
            "watermark": True,
            "export_disabled": False,
        },
        "enterprise": {
            "max_workflows": -1,
            "max_users": -1,
            "ai_calls_per_day": -1,
            "data_retention_days": -1,
            "watermark": False,
            "export_disabled": False,
        },
        "distribution": {
            "max_workflows": -1,
            "max_users": -1,
            "ai_calls_per_day": -1,
            "data_retention_days": -1,
            "watermark": False,
            "export_disabled": False,
        },
    }


# ──────────────────────────── 应用初始化 ────────────────────────────

app = Flask(__name__)
app.config["SECRET_KEY"] = Config.SECRET_KEY

# 确保数据目录存在
os.makedirs(os.path.dirname(Config.DB_PATH) or ".", exist_ok=True)
os.makedirs(os.path.dirname(Config.PRIVATE_KEY_PATH) or ".", exist_ok=True)


# ──────────────────────────── 数据库模块 ────────────────────────────

def get_db():
    """获取数据库连接（Flask g 作用域，每个请求独立）"""
    if "db" not in g:
        db = sqlite3.connect(Config.DB_PATH, check_same_thread=False)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        g.db = db
    return g.db


@app.teardown_appcontext
def close_db(exception):
    """请求结束后关闭数据库连接"""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """初始化数据库表结构（使用独立连接，不依赖 Flask g）"""
    conn = sqlite3.connect(Config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    db = conn
    db.executescript("""
        CREATE TABLE IF NOT EXISTS licenses (
            id TEXT PRIMARY KEY,
            license_id TEXT UNIQUE NOT NULL,
            product TEXT NOT NULL DEFAULT 'form-a',
            edition TEXT NOT NULL CHECK(edition IN ('community','enterprise','distribution')),
            issued_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            max_nodes INTEGER NOT NULL DEFAULT 1,
            features_json TEXT NOT NULL,
            machine_bindings_json TEXT NOT NULL DEFAULT '{}',
            distributor_json TEXT,
            is_revoked INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS activations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_fk TEXT NOT NULL,
            machine_fingerprint TEXT NOT NULL,
            client_host TEXT,
            client_version TEXT,
            activated_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_validated_at TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (license_fk) REFERENCES licenses(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            license_id TEXT,
            distributor_id TEXT,
            detail_json TEXT,
            ip_address TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_licenses_license_id ON licenses(license_id);
        CREATE INDEX IF NOT EXISTS idx_activations_fingerprint ON activations(machine_fingerprint);
        CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at);
    """)
    db.commit()


def log_audit(action, license_id=None, distributor_id=None, detail=None, ip=None):
    """写入审计日志"""
    try:
        db = get_db()
        db.execute(
            "INSERT INTO audit_log (action, license_id, distributor_id, detail_json, ip_address) VALUES (?, ?, ?, ?, ?)",
            (action, license_id, distributor_id, json.dumps(detail) if detail else None, ip),
        )
        db.commit()
    except Exception:
        pass  # 审计日志不应阻塞主流程


# ──────────────────────────── RSA 密钥管理 ────────────────────────────

def generate_rsa_keypair():
    """生成 RSA-2048 密钥对"""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    public_key = private_key.public_key()

    # 序列化私钥（PKCS#1 PEM 格式）
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # 序列化公钥
    pem_public = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return pem_private, pem_public


def load_or_generate_keys():
    """加载已有密钥对，或生成新的密钥对"""
    if os.path.exists(Config.PRIVATE_KEY_PATH) and os.path.exists(Config.PUBLIC_KEY_PATH):
        with open(Config.PRIVATE_KEY_PATH, "rb") as f:
            pem_private = f.read()
        with open(Config.PUBLIC_KEY_PATH, "rb") as f:
            pem_public = f.read()
        print(f"[INFO] 从文件加载密钥对: {Config.PRIVATE_KEY_PATH}")
    else:
        print("[INFO] 未找到密钥对，生成新的 RSA-2048 密钥对...")
        pem_private, pem_public = generate_rsa_keypair()
        with open(Config.PRIVATE_KEY_PATH, "wb") as f:
            f.write(pem_private)
        with open(Config.PUBLIC_KEY_PATH, "wb") as f:
            f.write(pem_public)
        print(f"[INFO] 私钥已保存: {Config.PRIVATE_KEY_PATH}")
        print(f"[INFO] 公钥已保存: {Config.PUBLIC_KEY_PATH}")

    private_key = serialization.load_pem_private_key(pem_private, password=None, backend=default_backend())
    public_key = serialization.load_pem_public_key(pem_public, backend=default_backend())

    return private_key, public_key


# 全局密钥对象
PRIVATE_KEY, PUBLIC_KEY = load_or_generate_keys()


def sign_data(data: dict) -> str:
    """用 RSA 私钥对 JSON 数据签名，返回 Base64 签名"""
    payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = PRIVATE_KEY.sign(
        payload,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return b64encode(signature).decode("utf-8")


def verify_signature(data: dict, signature_b64: str) -> bool:
    """用 RSA 公钥验证签名"""
    try:
        payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = b64decode(signature_b64.encode("utf-8"))
        PUBLIC_KEY.verify(
            signature,
            payload,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except InvalidSignature:
        return False
    except Exception:
        return False


# ──────────────────────────── License 文件构造 ────────────────────────────

def build_license_payload(
    license_id: str,
    edition: str,
    expires_at: str,
    max_nodes: int = 1,
    distributor_id: str = None,
    distributor_name: str = None,
    split_ratio: float = 0.0,
):
    """构建待签名的 License 数据载荷（不含签名）"""
    if edition == "community":
        features = Config.EDITION_FEATURES["community"].copy()
        machine_bindings = {"required": True, "max_bindings": 1, "current_bindings": []}
        distributor_data = None
    elif edition == "enterprise":
        features = Config.EDITION_FEATURES["enterprise"].copy()
        machine_bindings = {"required": True, "max_bindings": max_nodes, "current_bindings": []}
        distributor_data = None
    elif edition == "distribution":
        features = Config.EDITION_FEATURES["distribution"].copy()
        machine_bindings = {"required": True, "max_bindings": max_nodes, "current_bindings": []}
        distributor_data = {
            "id": distributor_id or "",
            "name": distributor_name or "",
            "split_ratio": split_ratio,
        }
    else:
        raise ValueError(f"Unknown edition: {edition}")

    payload = {
        "version": "1.0",
        "license_id": license_id,
        "product": "form-a",
        "edition": edition,
        "issued_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": expires_at,
        "max_nodes": max_nodes,
        "features": features,
        "machine_bindings": machine_bindings,
        "distributor": distributor_data,
    }
    return payload


def encode_license(payload: dict) -> str:
    """编码 License 为 Base64 字符串"""
    signature = sign_data(payload)
    signed_license = payload.copy()
    signed_license["signature"] = signature
    return b64encode(json.dumps(signed_license, ensure_ascii=False).encode("utf-8")).decode("utf-8")


def decode_license(license_b64: str) -> dict:
    """解码并验证 License Base64 字符串"""
    try:
        decoded = json.loads(b64decode(license_b64.encode("utf-8")).decode("utf-8"))
        return decoded
    except Exception as e:
        raise ValueError(f"Invalid license encoding: {e}")


# ──────────────────────────── 机器指纹 ────────────────────────────

def get_machine_fingerprint() -> dict:
    """获取当前机器的硬件指纹（跨平台）"""
    fingerprints = {}

    # --- CPU 序列号 ---
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                "wmic cpu get processorid", shell=True, timeout=5, stderr=subprocess.DEVNULL
            ).decode("utf-8", errors="ignore")
            for line in out.strip().splitlines():
                line = line.strip()
                if line and line.lower() != "processorid" and not line.startswith("processorid"):
                    fingerprints["cpu"] = line
                    break
        except Exception:
            fingerprints["cpu"] = hashlib.md5(platform.processor().encode()).hexdigest()[:16]
    elif sys.platform == "linux":
        try:
            out = subprocess.check_output(
                "dmidecode -t processor | grep 'ID:'", shell=True, timeout=5, stderr=subprocess.DEVNULL
            ).decode("utf-8", errors="ignore")
            cpu_id = out.strip().split("ID:")[-1].strip() if "ID:" in out else ""
            fingerprints["cpu"] = cpu_id if cpu_id else hashlib.md5(os.uname().machine.encode()).hexdigest()[:16]
        except Exception:
            fingerprints["cpu"] = "linux-cpu-unknown"
    elif sys.platform == "darwin":
        try:
            out = subprocess.check_output(
                "sysctl -n machdep.cpu.brand_string", shell=True, timeout=5, stderr=subprocess.DEVNULL
            ).decode("utf-8", errors="ignore").strip()
            fingerprints["cpu"] = hashlib.md5(out.encode()).hexdigest()[:16]
        except Exception:
            fingerprints["cpu"] = "mac-cpu-unknown"
    else:
        fingerprints["cpu"] = hashlib.md5(platform.node().encode()).hexdigest()[:16]

    # --- MAC 地址 ---
    import uuid as _uuid
    mac = hex(_uuid.getnode())
    fingerprints["mac"] = mac.replace("0x", "").upper()

    # --- 主板序列号 ---
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                "wmic baseboard get serialnumber", shell=True, timeout=5, stderr=subprocess.DEVNULL
            ).decode("utf-8", errors="ignore")
            for line in out.strip().splitlines():
                line = line.strip()
                if line and line.lower() != "serialnumber" and line != "To be filled by O.E.M.":
                    fingerprints["board"] = line
                    break
            if "board" not in fingerprints:
                fingerprints["board"] = "unknown-board"
        except Exception:
            fingerprints["board"] = "unknown-board"
    else:
        try:
            out = subprocess.check_output(
                "cat /sys/class/dmi/id/board_serial 2>/dev/null || echo unknown",
                shell=True, timeout=5, stderr=subprocess.DEVNULL
            ).decode("utf-8", errors="ignore").strip()
            fingerprints["board"] = out if out and out != "unknown" else "unknown-board"
        except Exception:
            fingerprints["board"] = "unknown-board"

    # --- 磁盘序列号 ---
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                "wmic diskdrive get serialnumber", shell=True, timeout=5, stderr=subprocess.DEVNULL
            ).decode("utf-8", errors="ignore")
            for line in out.strip().splitlines():
                line = line.strip()
                if line and line.lower() != "serialnumber" and line:
                    fingerprints["disk"] = line
                    break
            if "disk" not in fingerprints:
                fingerprints["disk"] = "unknown-disk"
        except Exception:
            fingerprints["disk"] = "unknown-disk"
    else:
        try:
            out = subprocess.check_output(
                "lsblk -o SERIAL 2>/dev/null | tail -1 | tr -d ' ' || echo unknown",
                shell=True, timeout=5, stderr=subprocess.DEVNULL
            ).decode("utf-8", errors="ignore").strip()
            fingerprints["disk"] = out if out else "unknown-disk"
        except Exception:
            fingerprints["disk"] = "unknown-disk"

    return fingerprints


def fingerprint_hash(fingerprints: dict) -> str:
    """生成指纹哈希（用于存储和比较）"""
    raw = "|".join([
        fingerprints.get("cpu", ""),
        fingerprints.get("mac", ""),
        fingerprints.get("board", ""),
        fingerprints.get("disk", ""),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fingerprints_match(stored_fingerprints: dict, current_fingerprints: dict) -> bool:
    """比较存储的指纹和当前的指纹（允许部分不匹配）"""
    fields = ["cpu", "mac", "board", "disk"]
    mismatches = 0
    for field in fields:
        stored = stored_fingerprints.get(field, "")
        current = current_fingerprints.get(field, "")
        if stored and current and stored != current:
            mismatches += 1
        # 如果某一方为空，不扣分
    return mismatches <= Config.MAX_FINGERPRINT_MISMATCH


# ──────────────────────────── 认证装饰器 ────────────────────────────

def require_admin_key(f):
    """要求 X-Admin-Key 请求头验证管理员身份"""
    @wraps(f)
    def decorated(*args, **kwargs):
        admin_key = request.headers.get("X-Admin-Key", "")
        expected_key = hashlib.sha256(
            (Config.SECRET_KEY + "admin").encode("utf-8")
        ).hexdigest()[:32]
        if not hmac.compare_digest(admin_key, expected_key):
            return jsonify({"error": "Unauthorized", "message": "无效的管理员密钥"}), 401
        return f(*args, **kwargs)
    return decorated


def require_license_token(f):
    """要求 X-License-Token 请求头（传入 license 的 Base64 编码）"""
    @wraps(f)
    def decorated(*args, **kwargs):
        license_b64 = request.headers.get("X-License-Token", "")
        if not license_b64:
            return jsonify({"error": "Missing License", "message": "缺少 License Token"}), 400
        try:
            kwargs["license_data"] = decode_license(license_b64)
        except ValueError as e:
            return jsonify({"error": "Invalid License", "message": str(e)}), 400
        return f(*args, **kwargs)
    return decorated


# ──────────────────────────── 辅助函数 ────────────────────────────

def check_license_validity(license_data: dict, check_fingerprint: bool = True) -> dict:
    """全面检查 License 有效性，返回检查结果"""
    result = {
        "valid": True,
        "reason": None,
        "details": {},
    }

    # 1. 验证签名
    signature = license_data.pop("signature", None)
    if not signature:
        result["valid"] = False
        result["reason"] = "缺少签名"
        return result
    if not verify_signature(license_data, signature):
        result["valid"] = False
        result["reason"] = "签名无效"
        return result
    result["details"]["signature"] = "verified"
    # 把签名加回去
    license_data["signature"] = signature

    # 2. 检查过期时间
    expires_at = license_data.get("expires_at", "")
    try:
        exp_time = datetime.datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ")
        if exp_time < datetime.datetime.utcnow():
            result["valid"] = False
            result["reason"] = "License 已过期"
            return result
    except ValueError:
        result["valid"] = False
        result["reason"] = "过期时间格式错误"
        return result
    result["details"]["expires_at"] = expires_at

    # 3. 检查是否被吊销
    db = get_db()
    row = db.execute(
        "SELECT is_revoked FROM licenses WHERE license_id = ?",
        (license_data.get("license_id"),),
    ).fetchone()
    if row and row["is_revoked"]:
        result["valid"] = False
        result["reason"] = "License 已被吊销"
        return result
    if not row and license_data.get("edition") != "community":
        result["valid"] = False
        result["reason"] = "License 未在服务器注册（客户端可能使用了未签发的许可）"
        return result

    # 4. 检查机器指纹（可选跳过，例如仅检查License本身时）
    if check_fingerprint:
        current_fp = get_machine_fingerprint()
        bindings = license_data.get("machine_bindings", {})
        stored_bindings = bindings.get("current_bindings", [])

        if bindings.get("required", True) and stored_bindings:
            # 检查当前指纹是否匹配已绑定集合中的任何一个
            matched = False
            for binding in stored_bindings:
                stored_parts = binding.get("fingerprints", {})
                if stored_parts and fingerprints_match(stored_parts, current_fp):
                    matched = True
                    break

            if not matched:
                # 如果没有超出最大绑定数，还是允许通过（激活时会创建绑定）
                max_b = bindings.get("max_bindings", 1)
                if len(stored_bindings) >= max_b:
                    result["valid"] = False
                    result["reason"] = "机器指纹不匹配且已达最大绑定数"
                    return result
                else:
                    result["details"]["fingerprint"] = "new_device_allowed"
            else:
                result["details"]["fingerprint"] = "matched"
        else:
            result["details"]["fingerprint"] = "no_binding_required"

    return result


# ──────────────────────────── API 路由 ────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    """健康检查"""
    return jsonify({
        "status": "ok",
        "service": "form-a-auth-server",
        "timestamp": datetime.datetime.utcnow().isoformat(),
    })


@app.route("/api/license/validate", methods=["POST"])
@require_license_token
def validate_license(license_data):
    """验证 License 有效性"""
    result = check_license_validity(license_data, check_fingerprint=True)
    return jsonify(result)


@app.route("/api/license/activate", methods=["POST"])
def activate_license():
    """
    首次激活 License，绑定机器指纹。
    请求体（JSON）：
    {
        "license": "BASE64_LICENSE",
        "client_version": "1.0.0",
        "customer_name": "某某公司"  // 可选
    }
    """
    data = request.get_json(silent=True) or {}
    license_b64 = data.get("license", "")
    client_version = data.get("client_version", "unknown")
    customer_name = data.get("customer_name", "")

    if not license_b64:
        return jsonify({"error": "Invalid Request", "message": "缺少 license 字段"}), 400

    # 解码 License
    try:
        license_data = decode_license(license_b64)
    except ValueError as e:
        return jsonify({"error": "Invalid License", "message": str(e)}), 400

    # 验证有效期和签名
    validation = check_license_validity(license_data, check_fingerprint=False)
    if not validation["valid"]:
        return jsonify({"error": "Activation Failed", "message": validation["reason"]}), 403

    # 检查是否已激活
    db = get_db()
    existing = db.execute(
        "SELECT id FROM licenses WHERE license_id = ?",
        (license_data["license_id"],),
    ).fetchone()

    if existing:
        # 已注册，检查是否已被其他机器绑定
        existing_bindings = db.execute(
            "SELECT machine_fingerprint FROM activations WHERE license_fk = ? AND is_active = 1",
            (existing["id"],),
        ).fetchall()
        current_fp = get_machine_fingerprint()
        current_fp_str = fingerprint_hash(current_fp)
        for binding in existing_bindings:
            if binding["machine_fingerprint"] != current_fp_str:
                # 不同的机器，检查绑定上限
                bindings_config = license_data.get("machine_bindings", {})
                max_bindings = bindings_config.get("max_bindings", 1)
                if len(existing_bindings) >= max_bindings:
                    return jsonify({"error": "Activation Failed",
                                    "message": f"已达最大绑定数 ({max_bindings})"}), 403

    # 获取当前机器指纹
    current_fp = get_machine_fingerprint()
    current_fp_str = fingerprint_hash(current_fp)

    # 更新 License 数据库（如有必要则插入）
    try:
        if not existing:
            db.execute(
                """INSERT INTO licenses (id, license_id, product, edition, issued_at, expires_at,
                   max_nodes, features_json, machine_bindings_json, distributor_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    license_data["license_id"],
                    license_data.get("product", "form-a"),
                    license_data["edition"],
                    license_data["issued_at"],
                    license_data["expires_at"],
                    license_data.get("max_nodes", 1),
                    json.dumps(license_data.get("features", {})),
                    json.dumps(license_data.get("machine_bindings", {})),
                    json.dumps(license_data["distributor"]) if license_data.get("distributor") else None,
                ),
            )
            license_db_id = db.execute(
                "SELECT id FROM licenses WHERE license_id = ?",
                (license_data["license_id"],),
            ).fetchone()["id"]
        else:
            license_db_id = existing["id"]

        # 记录激活
        db.execute(
            """INSERT INTO activations (license_fk, machine_fingerprint, client_host, client_version, last_validated_at)
               VALUES (?, ?, ?, ?, datetime('now'))""",
            (license_db_id, current_fp_str, request.remote_addr, client_version),
        )

        # 更新 License 中的绑定信息
        bindings = license_data.get("machine_bindings", {})
        bindings["current_bindings"] = bindings.get("current_bindings", []) + [
            {"fingerprints": current_fp, "bound_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}
        ]
        db.execute(
            "UPDATE licenses SET machine_bindings_json = ?, updated_at = datetime('now') WHERE id = ?",
            (json.dumps(bindings), license_db_id),
        )

        db.commit()

        # 审计日志
        log_audit(
            action="activate",
            license_id=license_data["license_id"],
            distributor_id=license_data.get("distributor", {}).get("id") if license_data.get("distributor") else None,
            detail={"fingerprint": current_fp, "customer": customer_name},
            ip=request.remote_addr,
        )

        return jsonify({
            "success": True,
            "message": "激活成功",
            "license_id": license_data["license_id"],
            "edition": license_data["edition"],
            "expires_at": license_data["expires_at"],
            "fingerprint": current_fp,
        }), 200

    except sqlite3.Error as e:
        db.rollback()
        return jsonify({"error": "Database Error", "message": str(e)}), 500


@app.route("/api/license/status", methods=["GET"])
def license_status():
    """
    查询当前授权状态。
    请求头: X-License-Token (Base64 License)
    """
    license_b64 = request.headers.get("X-License-Token", "")
    if not license_b64:
        # 无 License → 社区版（匿名）
        return jsonify({
            "edition": "community",
            "valid": True,
            "features": Config.EDITION_FEATURES["community"],
            "message": "使用社区版（无 License 文件）",
        }), 200

    try:
        license_data = decode_license(license_b64)
    except ValueError as e:
        return jsonify({"error": "Invalid License", "message": str(e)}), 400

    validation = check_license_validity(license_data, check_fingerprint=True)

    # 获取数据库中的激活记录
    db = get_db()
    row = db.execute(
        "SELECT * FROM licenses WHERE license_id = ?",
        (license_data["license_id"],),
    ).fetchone()

    activation_records = []
    if row:
        activations = db.execute(
            "SELECT * FROM activations WHERE license_fk = ? AND is_active = 1",
            (row["id"],),
        ).fetchall()
        activation_records = [
            {
                "activated_at": a["activated_at"],
                "last_validated_at": a["last_validated_at"],
                "client_version": a["client_version"],
            }
            for a in activations
        ]

    return jsonify({
        "valid": validation["valid"],
        "reason": validation["reason"],
        "edition": license_data.get("edition", "unknown"),
        "license_id": license_data.get("license_id"),
        "expires_at": license_data.get("expires_at"),
        "max_nodes": license_data.get("max_nodes", 1),
        "features": license_data.get("features", {}),
        "distributor": license_data.get("distributor"),
        "activations": activation_records,
        "offline_cache_days_remaining": Config.OFFLINE_CACHE_DAYS,
    }), (200 if validation["valid"] else 403)


@app.route("/api/license/renew", methods=["POST"])
@require_admin_key
def renew_license():
    """
    续期 License（管理员接口）。
    请求体（JSON）：
    {
        "license_id": "LIC-XXXX-XXXX",
        "new_expires_at": "2028-07-15T00:00:00Z",
        "new_max_nodes": 10,
        "distributor_id": "DIST-00123"  // 可选
    }
    """
    data = request.get_json(silent=True) or {}
    license_id = data.get("license_id", "")
    new_expires_at = data.get("new_expires_at", "")
    new_max_nodes = data.get("new_max_nodes")
    distributor_id = data.get("distributor_id")

    if not license_id or not new_expires_at:
        return jsonify({"error": "Invalid Request", "message": "缺少 license_id 或 new_expires_at"}), 400

    db = get_db()
    row = db.execute("SELECT * FROM licenses WHERE license_id = ?", (license_id,)).fetchone()
    if not row:
        return jsonify({"error": "Not Found", "message": "License 不存在"}), 404

    updates = ["expires_at = ?", "updated_at = datetime('now')"]
    params = [new_expires_at]

    if new_max_nodes is not None:
        updates.append("max_nodes = ?")
        params.append(new_max_nodes)

    params.append(license_id)
    db.execute(f"UPDATE licenses SET {', '.join(updates)} WHERE license_id = ?", params)

    # 记录续期审计
    expiry_date = data.get("new_expires_at")
    log_audit(
        action="renew",
        license_id=license_id,
        distributor_id=distributor_id,
        detail={"new_expires_at": new_expires_at, "new_max_nodes": new_max_nodes},
        ip=request.remote_addr,
    )
    db.commit()

    # 重新生成 License 文件（下发新文件用 - 返回编码后的 license）
    row = db.execute("SELECT * FROM licenses WHERE license_id = ?", (license_id,)).fetchone()
    features = json.loads(row["features_json"]) if row["features_json"] else {}
    bindings = json.loads(row["machine_bindings_json"]) if row["machine_bindings_json"] else {}
    distributor_data = json.loads(row["distributor_json"]) if row["distributor_json"] else None

    license_payload = {
        "version": "1.0",
        "license_id": row["license_id"],
        "product": row["product"],
        "edition": row["edition"],
        "issued_at": row["issued_at"],
        "expires_at": row["expires_at"],
        "max_nodes": row["max_nodes"],
        "features": features,
        "machine_bindings": bindings,
        "distributor": distributor_data,
    }
    new_license_b64 = encode_license(license_payload)

    return jsonify({
        "success": True,
        "message": "续期成功",
        "license_id": license_id,
        "new_expires_at": new_expires_at,
        "new_license_token": new_license_b64,
    }), 200


@app.route("/api/admin/licenses", methods=["GET"])
@require_admin_key
def admin_list_licenses():
    """管理员查询所有 License"""
    db = get_db()
    rows = db.execute(
        "SELECT * FROM licenses ORDER BY created_at DESC"
    ).fetchall()

    licenses = []
    for row in rows:
        features = json.loads(row["features_json"]) if row["features_json"] else {}
        distributor_data = json.loads(row["distributor_json"]) if row["distributor_json"] else None
        activation_count = db.execute(
            "SELECT COUNT(*) as cnt FROM activations WHERE license_fk = ? AND is_active = 1",
            (row["id"],),
        ).fetchone()["cnt"]

        licenses.append({
            "id": row["id"],
            "license_id": row["license_id"],
            "product": row["product"],
            "edition": row["edition"],
            "issued_at": row["issued_at"],
            "expires_at": row["expires_at"],
            "max_nodes": row["max_nodes"],
            "features": features,
            "distributor": distributor_data,
            "is_revoked": bool(row["is_revoked"]),
            "activation_count": activation_count,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        })

    return jsonify({
        "total": len(licenses),
        "licenses": licenses,
    }), 200


@app.route("/api/admin/generate", methods=["POST"])
@require_admin_key
def admin_generate_license():
    """
    生成新的 License 并由服务端签发。
    请求体（JSON）：
    {
        "edition": "enterprise" | "distribution" | "community",
        "expires_in_days": 365,
        "max_nodes": 5,
        "distributor_id": "DIST-00123",     // 仅分销版
        "distributor_name": "某某科技",       // 仅分销版
        "split_ratio": 0.30,                 // 仅分销版
        "license_id": "CUSTOM-LIC-001"       // 可选（不传则自动生成）
    }
    """
    data = request.get_json(silent=True) or {}
    edition = data.get("edition", "enterprise")
    expires_in_days = int(data.get("expires_in_days", 365))
    max_nodes = int(data.get("max_nodes", 1))
    distributor_id = data.get("distributor_id")
    distributor_name = data.get("distributor_name")
    split_ratio = float(data.get("split_ratio", 0.0))
    custom_license_id = data.get("license_id", "")

    if edition not in ("community", "enterprise", "distribution"):
        return jsonify({"error": "Invalid Edition", "message": f"不支持的版本: {edition}"}), 400

    # 生成 License ID
    if custom_license_id:
        license_id = custom_license_id
    else:
        prefix = {"community": "COM", "enterprise": "ENT", "distribution": "DIS"}[edition]
        license_id = f"{prefix}-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:4].upper()}"

    # 构造过期时间
    expires_at = (
        datetime.datetime.utcnow() + datetime.timedelta(days=expires_in_days)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 构建 License 载荷并签名
    payload = build_license_payload(
        license_id=license_id,
        edition=edition,
        expires_at=expires_at,
        max_nodes=max_nodes,
        distributor_id=distributor_id,
        distributor_name=distributor_name,
        split_ratio=split_ratio,
    )
    license_b64 = encode_license(payload)

    # 写入数据库
    db = get_db()
    try:
        db.execute(
            """INSERT INTO licenses (id, license_id, product, edition, issued_at, expires_at,
               max_nodes, features_json, machine_bindings_json, distributor_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                license_id,
                "form-a",
                edition,
                payload["issued_at"],
                payload["expires_at"],
                max_nodes,
                json.dumps(payload["features"]),
                json.dumps(payload["machine_bindings"]),
                json.dumps(payload["distributor"]) if payload.get("distributor") else None,
            ),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Duplicate", "message": f"License ID 已存在: {license_id}"}), 409

    log_audit(
        action="generate",
        license_id=license_id,
        distributor_id=distributor_id,
        detail={"edition": edition, "expires_in_days": expires_in_days, "max_nodes": max_nodes},
        ip=request.remote_addr,
    )

    return jsonify({
        "success": True,
        "license_id": license_id,
        "edition": edition,
        "issued_at": payload["issued_at"],
        "expires_at": payload["expires_at"],
        "max_nodes": max_nodes,
        "license_token": license_b64,  # 此 Base64 字符串即客户端需要的 License 文件
        "distributor": payload.get("distributor"),
    }), 201


@app.route("/api/admin/revoke", methods=["POST"])
@require_admin_key
def admin_revoke_license():
    """吊销 License"""
    data = request.get_json(silent=True) or {}
    license_id = data.get("license_id", "")
    reason = data.get("reason", "")

    if not license_id:
        return jsonify({"error": "Invalid Request", "message": "缺少 license_id"}), 400

    db = get_db()
    row = db.execute("SELECT id FROM licenses WHERE license_id = ?", (license_id,)).fetchone()
    if not row:
        return jsonify({"error": "Not Found", "message": "License 不存在"}), 404

    db.execute("UPDATE licenses SET is_revoked = 1, updated_at = datetime('now') WHERE license_id = ?", (license_id,))
    db.execute(
        "UPDATE activations SET is_active = 0 WHERE license_fk = ?",
        (row["id"],),
    )
    db.commit()

    log_audit(
        action="revoke",
        license_id=license_id,
        detail={"reason": reason},
        ip=request.remote_addr,
    )

    return jsonify({"success": True, "message": f"License {license_id} 已吊销"}), 200


@app.route("/api/admin/audit-log", methods=["GET"])
@require_admin_key
def admin_audit_log():
    """查询审计日志"""
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)

    db = get_db()
    rows = db.execute(
        "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()

    logs = [
        {
            "id": r["id"],
            "action": r["action"],
            "license_id": r["license_id"],
            "distributor_id": r["distributor_id"],
            "detail": json.loads(r["detail_json"]) if r["detail_json"] else None,
            "ip_address": r["ip_address"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]

    total = db.execute("SELECT COUNT(*) as cnt FROM audit_log").fetchone()["cnt"]

    return jsonify({"total": total, "logs": logs}), 200


@app.route("/api/license/generate-endpoint", methods=["GET"])
def get_public_key():
    """
    客户端获取公钥（用于本地验签）。
    注意：生产环境应通过安全通道分发公钥，或嵌入客户端二进制。
    """
    with open(Config.PUBLIC_KEY_PATH, "r") as f:
        pub_key_pem = f.read()
    return jsonify({
        "algorithm": "RSA-2048 SHA-256",
        "public_key_pem": pub_key_pem,
    })


# ──────────────────────────── 客户端验证模块 ────────────────────────────

class LicenseClient:
    """
    客户端验证器（可供 Form-A 应用集成）。

    用法:
        client = LicenseClient("/path/to/license.lic", auth_server_url="http://auth:5000")
        status = client.validate()
        if status["valid"]:
            features = status["features"]
    """

    def __init__(self, license_file_path: str, auth_server_url: str = None, public_key_pem: str = None):
        self.license_file_path = license_file_path
        self.auth_server_url = auth_server_url
        self.cache_file = license_file_path + ".cache"
        self._cache = self._load_cache()

        if public_key_pem:
            self.public_key = serialization.load_pem_public_key(
                public_key_pem.encode("utf-8"), backend=default_backend()
            )
        else:
            self.public_key = PUBLIC_KEY  # 使用服务端全局公钥

        if not os.path.exists(self.cache_file):
            self._cache = {}

    def _load_cache(self) -> dict:
        """加载离线缓存"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_cache(self, cache: dict):
        """保存离线缓存"""
        try:
            with open(self.cache_file, "w") as f:
                json.dump(cache, f)
        except IOError:
            pass

    def _local_verify(self, license_data: dict) -> dict:
        """本地验证 License（验签 + 过期 + 机器指纹）"""
        result = {"valid": True, "reason": None, "features": None}

        # 验签
        signature = license_data.get("signature", "")
        if not signature:
            result["valid"] = False
            result["reason"] = "缺少签名"
            return result

        payload = {k: v for k, v in license_data.items() if k != "signature"}
        sig_bytes = b64decode(signature.encode("utf-8"))
        payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        try:
            self.public_key.verify(sig_bytes, payload_bytes, padding.PKCS1v15(), hashes.SHA256())
        except InvalidSignature:
            result["valid"] = False
            result["reason"] = "签名无效"
            return result

        # 检查过期
        expires_at = license_data.get("expires_at", "")
        try:
            exp_time = datetime.datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ")
            if exp_time < datetime.datetime.utcnow():
                result["valid"] = False
                result["reason"] = "License 已过期"
                return result
        except ValueError:
            result["valid"] = False
            result["reason"] = "过期时间格式错误"
            return result

        # 机器指纹检查（记录在本地缓存中）
        current_fp = get_machine_fingerprint()
        cache = self._cache or {}
        stored_fp = cache.get("fingerprint", {})
        if stored_fp and not fingerprints_match(stored_fp, current_fp):
            result["valid"] = False
            result["reason"] = "机器指纹不匹配"
            return result

        # 提取功能边界
        edition = license_data.get("edition", "community")
        result["features"] = license_data.get("features", Config.EDITION_FEATURES.get(edition, {}))
        result["edition"] = edition
        result["license_id"] = license_data.get("license_id")
        result["expires_at"] = expires_at
        result["distributor"] = license_data.get("distributor")

        return result

    def validate(self) -> dict:
        """
        执行完整验证流程：
        1) 尝试联网校验
        2) 联网失败→本地验签+过期检查
        3) 断网超过7天→限制
        """
        if not os.path.exists(self.license_file_path):
            # 无 License 文件 → 社区版
            return {
                "valid": True,
                "edition": "community",
                "features": Config.EDITION_FEATURES["community"],
                "message": "未检测到 License 文件，使用社区版",
            }

        # 读取 License 文件
        try:
            with open(self.license_file_path, "r") as f:
                license_b64 = f.read().strip()
            license_data = decode_license(license_b64)
        except (IOError, ValueError) as e:
            return {"valid": False, "reason": f"License 文件读取失败: {e}"}

        # 检查离线天数
        cache = self._cache or {}
        last_online = cache.get("last_online_check")
        now_ts = time.time()

        # 先执行本地验证
        local_result = self._local_verify(license_data)
        if not local_result["valid"]:
            return local_result

        if last_online:
            days_offline = (now_ts - last_online) / 86400
            if days_offline > Config.OFFLINE_CACHE_DAYS:
                return {
                    "valid": False,
                    "reason": f"已离线超过 {Config.OFFLINE_CACHE_DAYS} 天，需要联网重新验证",
                    "edition": local_result.get("edition"),
                    "features": local_result.get("features"),
                }

        # 尝试联网校验（每7天一次）
        should_online_check = (
            not last_online or (now_ts - last_online) > Config.LICENSE_CHECK_INTERVAL_DAYS * 86400
        )
        online_valid = None
        if should_online_check and self.auth_server_url:
            try:
                import urllib.request
                req = urllib.request.Request(
                    f"{self.auth_server_url}/api/license/validate",
                    data=json.dumps({"license": license_b64}).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "X-License-Token": license_b64,
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                online_valid = resp_data.get("valid", False)

                # 更新缓存
                cache["last_online_check"] = now_ts
                cache["fingerprint"] = get_machine_fingerprint()
                cache["online_valid"] = online_valid
                self._save_cache(cache)
            except Exception:
                # 联网失败，使用本地缓存
                online_valid = cache.get("online_valid", True)

        # 更新缓存
        if not last_online:
            cache["last_online_check"] = now_ts
            cache["fingerprint"] = get_machine_fingerprint()
            self._save_cache(cache)

        local_result["offline_cache_remaining_days"] = (
            Config.OFFLINE_CACHE_DAYS - (now_ts - (cache.get("last_online_check", now_ts))) / 86400
            if cache.get("last_online_check") else Config.OFFLINE_CACHE_DAYS
        )
        local_result["online_valid"] = online_valid if online_valid is not None else True

        return local_result


# ──────────────────────────── 入口 ────────────────────────────

def main():
    """应用入口"""
    print("=" * 60)
    print("  Form-A 授权验证服务 (auth-server)")
    print("=" * 60)
    print(f"  数据库     : {Config.DB_PATH}")
    print(f"  密钥对     : {Config.PRIVATE_KEY_PATH}")
    print(f"  监听地址   : {Config.HOST}:{Config.PORT}")
    print(f"  密钥算法   : RSA-2048 + SHA-256")
    print(f"  离线缓存   : {Config.OFFLINE_CACHE_DAYS} 天")
    print(f"  功能版本   : community / enterprise / distribution")
    print("-" * 60)
    print()

    init_db()
    app.run(host=Config.HOST, port=Config.PORT, debug=False)


if __name__ == "__main__":
    main()
