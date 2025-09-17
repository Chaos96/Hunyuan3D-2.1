# 🔐 HTTPS SSL Setup Guide for Hunyuan3D

解决浏览器显示"危险，无法展示"的完整指南

## 🚨 问题说明

当使用自签名SSL证书时，浏览器会显示安全警告，阻止访问网站。这是正常的安全机制。

## 🛠️ 解决方案

### 方案1: 浏览器绕过安全警告（最快）

#### Chrome/Edge浏览器:
1. 看到安全警告页面时，点击 **"高级"**
2. 点击 **"继续前往 localhost (不安全)"**
3. 或者在警告页面直接输入: `thisisunsafe` (不会显示输入，直接打字即可)

#### Firefox浏览器:
1. 点击 **"高级"**
2. 点击 **"接受风险并继续"**

#### Safari浏览器:
1. 点击 **"显示详细信息"**
2. 点击 **"访问此网站"**
3. 在对话框中点击 **"访问网站"**

### 方案2: 使用Let's Encrypt证书（推荐生产环境）

```bash
# 自动获取Let's Encrypt证书
python3 setup_ssl.py --letsencrypt --domain yourdomain.com --email your@email.com

# 然后启动HTTPS服务器
python3 gradio_app_lazy.py --ssl --port 443 --low_vram_mode
```

**要求:**
- 你的域名必须指向当前服务器
- 端口80必须对外网开放
- 服务器必须有公网IP

### 方案3: 生成改进的自签名证书

```bash
# 生成自签名证书
python3 setup_ssl.py --self-signed --domain localhost

# 查看绕过指南
python3 setup_ssl.py --instructions
```

### 方案4: HTTP模式（最简单）

如果不需要HTTPS，直接使用HTTP模式：

```bash
# 使用HTTP启动（默认端口80）
./start_http.sh

# 或指定端口
./start_http.sh --port 8080
```

然后访问: `http://localhost:8080`

## 🔧 详细使用说明

### SSL设置工具

```bash
# 查看帮助
python3 setup_ssl.py --help

# 生成自签名证书
python3 setup_ssl.py --self-signed --domain localhost

# Let's Encrypt证书（需要域名）
python3 setup_ssl.py --letsencrypt --domain example.com --email admin@example.com

# 显示浏览器绕过说明
python3 setup_ssl.py --instructions
```

### 启动选项

```bash
# HTTPS模式（自动生成证书）
./start_https.sh

# HTTPS模式（使用现有证书）
python3 gradio_app_lazy.py --ssl --ssl-cert ./certs/cert.pem --ssl-key ./certs/key.pem

# HTTP模式
./start_http.sh
```

## ⚡ 快速解决方案

如果你只是想快速测试，推荐这个流程：

1. **启动HTTP服务器:**
```bash
./start_http.sh --port 8080
```

2. **访问地址:**
```
http://localhost:8080
```

3. **如果一定要用HTTPS:**
```bash
./start_https.sh
# 然后在浏览器警告页面输入: thisisunsafe
```

## 🌐 生产环境建议

对于生产环境，强烈建议：

1. **使用真实域名和Let's Encrypt证书:**
```bash
python3 setup_ssl.py --letsencrypt --domain yourdomain.com --email your@email.com
```

2. **配置反向代理 (nginx/apache):**
```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

3. **使用防火墙开放必要端口:**
```bash
# 开放HTTPS端口
sudo ufw allow 443/tcp
# 开放HTTP端口（用于Let's Encrypt验证）
sudo ufw allow 80/tcp
```

## 🛡️ 安全注意事项

- **自签名证书**: 仅适用于开发和测试环境
- **生产环境**: 必须使用受信任的CA签发的证书
- **防火墙**: 确保只开放必要的端口
- **定期更新**: Let's Encrypt证书90天过期，需要自动续期

## 🆘 常见问题

**Q: 为什么浏览器显示"不安全"？**
A: 自签名证书不被浏览器信任，这是正常的安全机制。

**Q: 如何让证书被信任？**
A: 使用Let's Encrypt或购买商业SSL证书。

**Q: iframe还是显示空白？**
A: 确保使用了安全的模板文件，并检查浏览器控制台的错误信息。

**Q: 能否不用HTTPS？**
A: 可以，使用 `./start_http.sh` 启动HTTP服务器即可。