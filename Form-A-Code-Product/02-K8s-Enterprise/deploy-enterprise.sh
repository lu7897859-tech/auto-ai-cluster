#!/usr/bin/env bash
# ============================================================================
# Form-A 企业版 K8s 一键部署脚本
# 版本: v1.0 | 更新日期: 2026-07-15
# 适用环境: Kubernetes ≥ 1.28, Helm ≥ 3.12
# ============================================================================

set -euo pipefail

# ─── 颜色定义 ──────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ─── 默认配置 ──────────────────────────────────────────────────────────────
NAMESPACE="${FORM_A_NAMESPACE:-form-a-system}"
RELEASE_NAME="${FORM_A_RELEASE:-form-a-enterprise}"
CHART_REPO="${FORM_A_CHART_REPO:-https://helm.form-a.io/enterprise}"
CHART_NAME="${FORM_A_CHART_NAME:-form-a/ai-cluster-enterprise}"
VALUES_FILE="${FORM_A_VALUES_FILE:-form-a-values.yaml}"
VERSION="${FORM_A_VERSION:-}"
DOMAIN="${FORM_A_DOMAIN:-form-a.example.com}"
STORAGE_CLASS="${FORM_A_STORAGE_CLASS:-standard}"

LOG_FILE="form-a-deploy-$(date +%Y%m%d_%H%M%S).log"

# ─── 辅助函数 ──────────────────────────────────────────────────────────────

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $*" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" | tee -a "$LOG_FILE"
}

divider() {
    echo "─────────────────────────────────────────────────────────────────" | tee -a "$LOG_FILE"
}

check_cmd() {
    local cmd="$1"
    local hint="${2:-请安装 $cmd}"
    if ! command -v "$cmd" &> /dev/null; then
        log_error "未找到命令: $cmd — $hint"
        exit 1
    fi
    log_success "$cmd 可用 ($(command -v "$cmd"))"
}

banner() {
    cat << 'EOF'
    ______                    __    __          _       _
   / ____/___  ___  ____     / /   / /___ ___  (_)___  (_)
  / /_  / __ \/ _ \/ __ \   / /   / / __ `__ \/ / __ \/ /
 / __/ / /_/ /  __/ / / /  / /___/ / / / / / / / / / / /
/_/    \____/\___/_/ /_/  /_____/_/_/ /_/ /_/_/_/ /_/_/

  Form-A Enterprise K8s Deployment Script v1.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EOF
}

# ═══════════════════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════════════════

main() {
    banner
    echo -e "${CYAN}日志文件:${NC} $LOG_FILE"
    echo ""

    # ─── 步骤 1: 检查 kubectl ──────────────────────────────────────────────
    divider
    log_info "步骤 1/6: 检查 Kubernetes 环境 (kubectl)"

    check_cmd "kubectl" "请先安装 kubectl (https://kubernetes.io/docs/tasks/tools/)"

    # 检查集群连接
    if ! kubectl cluster-info &> /dev/null; then
        log_error "无法连接 Kubernetes 集群。请检查:"
        echo "  - kubeconfig 是否正确配置 (kubectl config view)"
        echo "  - 集群是否正常运行"
        echo "  - 当前上下文是否正确 (kubectl config current-context)"
        exit 1
    fi
    log_success "Kubernetes 集群连接正常"

    # 检查集群版本
    local k8s_version
    k8s_version=$(kubectl version --short 2>/dev/null | grep Server | awk '{print $NF}' || kubectl version -o json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['serverVersion']['gitVersion'])" 2>/dev/null || echo "unknown")
    log_info "Kubernetes 版本: $k8s_version"

    # 检查节点状态
    local nodes_ready
    nodes_ready=$(kubectl get nodes --no-headers 2>/dev/null | grep -c " Ready" || echo 0)
    if [ "$nodes_ready" -lt 1 ]; then
        log_error "没有 Ready 状态的节点！请检查集群状态"
        exit 1
    fi
    log_success "节点状态: $nodes_ready 个节点 Ready"

    # ─── 步骤 2: 检查 Helm ────────────────────────────────────────────────
    divider
    log_info "步骤 2/6: 检查 Helm"

    check_cmd "helm" "请先安装 Helm (https://helm.sh/docs/intro/install/)"

    local helm_version
    helm_version=$(helm version --short 2>/dev/null || helm version 2>/dev/null | head -1)
    log_info "Helm 版本: $helm_version"

    # ─── 步骤 3: 检查并创建命名空间 ──────────────────────────────────────
    divider
    log_info "步骤 3/6: 检查命名空间 — ${NAMESPACE}"

    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_info "命名空间 '${NAMESPACE}' 已存在，跳过创建"
    else
        log_info "创建命名空间 '${NAMESPACE}'..."
        kubectl create namespace "$NAMESPACE"
        log_success "命名空间 '${NAMESPACE}' 创建成功"
    fi

    # 创建数据层命名空间
    local data_ns="${FORM_A_DATA_NAMESPACE:-form-a-data}"
    if ! kubectl get namespace "$data_ns" &> /dev/null; then
        log_info "创建数据层命名空间 '${data_ns}'..."
        kubectl create namespace "$data_ns"
        log_success "命名空间 '${data_ns}' 创建成功"
    fi

    # ─── 步骤 3b: 检查 License Secret ────────────────────────────────────
    divider
    log_info "步骤 3b/6: 检查 License 配置"

    local license_secret="${FORM_A_LICENSE_SECRET:-form-a-license}"
    if kubectl get secret "$license_secret" -n "$NAMESPACE" &> /dev/null; then
        log_success "License Secret '${license_secret}' 就绪"
    else
        log_warn "未找到 License Secret '${license_secret}'"
        log_warn "请确保 License 文件已准备好，安装后需手动创建 Secret:"
        echo "  kubectl create secret generic ${license_secret} \\"
        echo "    --namespace ${NAMESPACE} \\"
        echo "    --from-file=license.key=/path/to/license.key"
        echo ""
        echo -n "继续安装？(y/N): "
        read -r confirm
        if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
            log_info "部署已取消"
            exit 0
        fi
    fi

    # ─── 步骤 4: 添加 Helm 仓库并安装 ──────────────────────────────────
    divider
    log_info "步骤 4/6: 部署 Form-A 企业版"

    # 添加仓库
    log_info "添加 Helm 仓库: ${CHART_REPO}"
    helm repo add form-a "$CHART_REPO" 2>/dev/null || helm repo update form-a
    helm repo update
    log_success "Helm 仓库更新完成"

    # 构建安装参数
    local install_args=(
        "$RELEASE_NAME" "$CHART_NAME"
        --namespace "$NAMESPACE"
        --create-namespace
    )

    # 如果存在自定义 values 文件，使用它
    if [ -f "$VALUES_FILE" ]; then
        log_info "使用自定义 values 文件: ${VALUES_FILE}"
        install_args+=(--values "$VALUES_FILE")
    else
        log_warn "未找到自定义 values 文件 '${VALUES_FILE}'，使用默认值"
    fi

    # 设置域名
    install_args+=(--set "global.domain=${DOMAIN}")
    install_args+=(--set "global.storageClass=${STORAGE_CLASS}")

    # 指定版本
    if [ -n "$VERSION" ]; then
        install_args+=(--version "$VERSION")
    fi

    # 执行安装
    log_info "执行 helm install..."
    helm install "${install_args[@]}" 2>&1 | tee -a "$LOG_FILE"

    local helm_exit=${PIPESTATUS[0]}
    if [ $helm_exit -ne 0 ]; then
        log_error "Helm install 失败 (exit: $helm_exit)"
        log_error "请查看日志 $LOG_FILE 排查错误"
        log_error "常见原因:"
        echo "  - Chart 版本不存在或不兼容"
        echo "  - StorageClass 不存在"
        echo "  - 资源配额不足"
        exit $helm_exit
    fi
    log_success "Helm install 成功"

    # ─── 步骤 5: 等待 Pod 就绪 ──────────────────────────────────────────
    divider
    log_info "步骤 5/6: 等待所有 Pod 就绪"

    local timeout_seconds="${FORM_A_TIMEOUT:-300}"
    log_info "最长等待: ${timeout_seconds} 秒"

    # 等待所有 Deployment 就绪
    if kubectl wait --for=condition=available deployment \
        --all -n "$NAMESPACE" --timeout="${timeout_seconds}s" 2>&1 | tee -a "$LOG_FILE"; then
        log_success "所有 Deployment 已就绪"
    else
        log_warn "部分 Deployment 未就绪（可能 StatefulSet 还在启动中）"
    fi

    # 等待 StatefulSet
    if kubectl wait --for=condition=ready pod \
        -l "app.kubernetes.io/component=postgres-patroni" \
        -n "$data_ns" --timeout="${timeout_seconds}s" 2>&1 | tee -a "$LOG_FILE"; then
        log_success "PostgreSQL 集群就绪"
    else
        log_warn "PostgreSQL 可能仍在启动中，请稍后检查"
    fi

    # 检查核心组件状态
    local pending_count
    pending_count=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | grep -v Running | grep -v Completed | wc -l | tr -d ' ')
    if [ "$pending_count" -gt 0 ]; then
        log_warn "仍有 ${pending_count} 个 Pod 未正常运行"
        kubectl get pods -n "$NAMESPACE" 2>&1 | tee -a "$LOG_FILE"
    else
        log_success "所有 Pod 正常运行"
    fi

    # ─── 步骤 6: 输出访问地址 ──────────────────────────────────────────
    divider
    log_info "步骤 6/6: 输出访问地址"

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              Form-A 企业版部署完成！                   ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # 获取 Ingress 地址
    local ingress_host
    ingress_host=$(kubectl get ingress -n "$NAMESPACE" -o jsonpath='{.items[0].spec.rules[0].host}' 2>/dev/null || echo "$DOMAIN")

    # 获取 LoadBalancer 地址（如果没有 Ingress）
    local lb_host
    lb_host=$(kubectl get svc -n ingress-nginx ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || \
              kubectl get svc -n ingress-nginx ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || \
              echo "待配置")

    echo -e "  ${CYAN}管理控制台:${NC}   https://${ingress_host}"
    echo -e "  ${CYAN}n8n 工作台:${NC}    https://${ingress_host}/n8n"
    echo -e "  ${CYAN}API 网关:${NC}      https://${ingress_host}/api"
    echo ""
    echo -e "  ${YELLOW}默认管理员账号:${NC} admin@form-a.io"
    echo -e "  ${YELLOW}默认管理员密码:${NC} 查看 Secret"
    echo ""
    echo "    获取密码:"
    echo "    kubectl get secret ${RELEASE_NAME}-admin-password \\"
    echo "      -n ${NAMESPACE} -o jsonpath='{.data.password}' | base64 -d"
    echo ""
    echo -e "  ${CYAN}LoadBalancer IP:${NC} ${lb_host}"
    echo ""

    if [ "$ingress_host" != "$DOMAIN" ]; then
        log_info "本地测试可添加 hosts 记录:"
        echo "    echo '<LB_IP> ${ingress_host}' >> /etc/hosts"
    fi

    # ─── 汇总 ──────────────────────────────────────────────────────────
    divider
    log_success "部署完成！日志文件: $LOG_FILE"
    echo ""
    echo -e "  ${GREEN}查看所有 Pod:${NC}"
    echo "    kubectl get pods -n ${NAMESPACE} -o wide"
    echo "    kubectl get pods -n ${data_ns} -o wide"
    echo ""
    echo -e "  ${GREEN}查看 Helm Release:${NC}"
    echo "    helm list -n ${NAMESPACE}"
    echo ""
    echo -e "  ${GREEN}查看日志:${NC}"
    echo "    kubectl logs -n ${NAMESPACE} -l app.kubernetes.io/component=n8n-worker --tail=100"
    echo ""
}

# ─── 执行主流程 ──────────────────────────────────────────────────────────
main "$@"
