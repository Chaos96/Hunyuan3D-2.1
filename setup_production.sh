#!/bin/bash

# Hunyuan3D生产环境配置脚本
# 自动配置nginx反向代理和Let's Encrypt SSL证书

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为root用户
check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "请不要使用root用户运行此脚本"
        print_status "使用普通用户运行，脚本会在需要时请求sudo权限"
        exit 1
    fi
}

# 检查系统
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
    else
        print_error "无法检测操作系统"
        exit 1
    fi
    print_status "检测到系统: $OS $VER"
}

# 安装依赖
install_dependencies() {
    print_status "安装系统依赖..."

    if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
        sudo apt-get update
        sudo apt-get install -y nginx certbot python3-certbot-nginx
    elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]]; then
        sudo yum update -y
        sudo yum install -y nginx certbot python3-certbot-nginx
    elif [[ "$OS" == *"Fedora"* ]]; then
        sudo dnf update -y
        sudo dnf install -y nginx certbot python3-certbot-nginx
    else
        print_error "不支持的操作系统: $OS"
        exit 1
    fi

    print_success "系统依赖安装完成"
}

# 配置nginx
setup_nginx() {
    local domain=$1
    local app_port=$2

    print_status "配置nginx反向代理..."

    # 创建nginx配置
    cat > "/tmp/hunyuan3d" << EOF
server {
    listen 80;
    server_name $domain www.$domain;

    # Let's Encrypt验证
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # 其他请求重定向到HTTPS（SSL证书获取后生效）
    location / {
        proxy_pass http://127.0.0.1:$app_port;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # 临时允许HTTP访问
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_cache_bypass \$http_upgrade;
    }

    # 静态文件
    location /static/ {
        proxy_pass http://127.0.0.1:$app_port;
        proxy_set_header Host \$host;
        expires 1h;
    }
}
EOF

    # 复制配置文件
    sudo mv "/tmp/hunyuan3d" "/etc/nginx/sites-available/hunyuan3d"

    # 创建软链接
    sudo ln -sf "/etc/nginx/sites-available/hunyuan3d" "/etc/nginx/sites-enabled/"

    # 移除默认配置
    sudo rm -f "/etc/nginx/sites-enabled/default"

    # 测试nginx配置
    sudo nginx -t
    if [[ $? -eq 0 ]]; then
        print_success "nginx配置验证成功"
    else
        print_error "nginx配置验证失败"
        exit 1
    fi

    # 重启nginx
    sudo systemctl restart nginx
    sudo systemctl enable nginx

    print_success "nginx配置完成"
}

# 获取SSL证书
setup_ssl() {
    local domain=$1
    local email=$2

    print_status "获取Let's Encrypt SSL证书..."

    # 确保nginx正在运行
    sudo systemctl start nginx

    # 获取证书
    sudo certbot --nginx -d "$domain" -d "www.$domain" --email "$email" --agree-tos --no-eff-email --redirect

    if [[ $? -eq 0 ]]; then
        print_success "SSL证书获取成功"

        # 设置自动续期
        (crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet") | crontab -
        print_success "SSL证书自动续期已设置"
    else
        print_error "SSL证书获取失败"
        print_warning "继续使用HTTP模式"
        return 1
    fi
}

# 配置防火墙
setup_firewall() {
    print_status "配置防火墙..."

    if command -v ufw >/dev/null 2>&1; then
        sudo ufw allow 22/tcp
        sudo ufw allow 80/tcp
        sudo ufw allow 443/tcp
        sudo ufw --force enable
        print_success "UFW防火墙配置完成"
    elif command -v firewall-cmd >/dev/null 2>&1; then
        sudo firewall-cmd --permanent --add-service=ssh
        sudo firewall-cmd --permanent --add-service=http
        sudo firewall-cmd --permanent --add-service=https
        sudo firewall-cmd --reload
        print_success "firewalld防火墙配置完成"
    else
        print_warning "未找到防火墙管理工具，请手动配置防火墙"
    fi
}

# 创建systemd服务
create_service() {
    local app_port=$1
    local app_dir=$(pwd)

    print_status "创建systemd服务..."

    cat > "/tmp/hunyuan3d.service" << EOF
[Unit]
Description=Hunyuan3D 3D Generation Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$app_dir
ExecStart=/usr/bin/python3 $app_dir/gradio_app_lazy.py --port $app_port --host 127.0.0.1 --low_vram_mode
Restart=always
RestartSec=10
Environment=PYTHONPATH=$app_dir

[Install]
WantedBy=multi-user.target
EOF

    sudo mv "/tmp/hunyuan3d.service" "/etc/systemd/system/"
    sudo systemctl daemon-reload
    sudo systemctl enable hunyuan3d

    print_success "systemd服务创建完成"
}

# 主函数
main() {
    echo "🚀 Hunyuan3D生产环境配置脚本"
    echo "================================"

    # 检查参数
    if [[ $# -lt 2 ]]; then
        echo "使用方法: $0 <domain> <email> [app_port]"
        echo "例如: $0 hunyuan3d.example.com admin@example.com 8080"
        exit 1
    fi

    local domain=$1
    local email=$2
    local app_port=${3:-8080}

    print_status "配置参数:"
    print_status "  域名: $domain"
    print_status "  邮箱: $email"
    print_status "  应用端口: $app_port"

    read -p "确认配置并继续? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "已取消"
        exit 0
    fi

    check_root
    detect_os
    install_dependencies
    setup_nginx "$domain" "$app_port"
    setup_firewall
    create_service "$app_port"

    # 启动应用服务
    print_status "启动Hunyuan3D服务..."
    sudo systemctl start hunyuan3d

    # 等待应用启动
    print_status "等待应用启动..."
    sleep 10

    # 检查应用状态
    if curl -s "http://127.0.0.1:$app_port" > /dev/null; then
        print_success "应用启动成功"

        # 获取SSL证书
        if setup_ssl "$domain" "$email"; then
            print_success "🎉 生产环境配置完成!"
            print_success "访问地址: https://$domain"
        else
            print_success "🎉 HTTP模式配置完成!"
            print_success "访问地址: http://$domain"
            print_warning "SSL证书获取失败，请检查域名DNS设置"
        fi
    else
        print_error "应用启动失败，请检查配置"
        sudo systemctl status hunyuan3d
        exit 1
    fi

    print_status ""
    print_status "管理命令:"
    print_status "  查看应用状态: sudo systemctl status hunyuan3d"
    print_status "  重启应用: sudo systemctl restart hunyuan3d"
    print_status "  查看日志: sudo journalctl -u hunyuan3d -f"
    print_status "  更新SSL证书: sudo certbot renew"
}

main "$@"