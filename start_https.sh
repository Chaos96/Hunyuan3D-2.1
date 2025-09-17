#!/bin/bash

# Hunyuan3D HTTPS Server Startup Script
# This script starts the Hunyuan3D server with HTTPS support using Let's Encrypt certificates

echo "🚀 Starting Hunyuan3D with HTTPS support..."
echo "================================"

# Check if cryptography package is installed
python3 -c "import cryptography" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 Installing cryptography package for SSL support..."
    pip install cryptography
fi

# Certificate paths
CERT_DIR="certs-fast3d"
SSL_CERT="$CERT_DIR/fullchain.pem"
SSL_KEY="$CERT_DIR/privkey.pem"

# Check if certificates exist
if [ ! -f "$SSL_CERT" ] || [ ! -f "$SSL_KEY" ]; then
    echo "❌ ERROR: SSL certificates not found!"
    echo ""
    echo "Expected certificate files:"
    echo "  - $SSL_CERT"
    echo "  - $SSL_KEY"
    echo ""
    echo "Please run one of the following to obtain certificates:"
    echo "  1. sudo ./certs-fast3d/request_certificate_cloudflare.sh (recommended)"
    echo "  2. sudo ./certs-fast3d/request_certificate_dns.sh"
    echo "  3. sudo ./certs-fast3d/request_certificate.sh (requires port 80)"
    echo ""
    exit 1
fi

# Verify certificate validity
echo "🔐 Checking SSL certificate..."
openssl x509 -in "$SSL_CERT" -noout -checkend 0 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  WARNING: SSL certificate appears to be expired!"
    echo "Please renew your certificate with:"
    echo "  sudo ./certs-fast3d/renew_certificate.sh"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    # Show certificate info
    DOMAIN=$(openssl x509 -in "$SSL_CERT" -noout -subject | sed -n 's/.*CN=\([^/]*\).*/\1/p')
    EXPIRY=$(openssl x509 -in "$SSL_CERT" -noout -enddate | cut -d= -f2)
    echo "✅ Certificate valid for: $DOMAIN"
    echo "   Expires on: $EXPIRY"
fi

# Default arguments
MODEL_PATH="tencent/Hunyuan3D-2.1"
SUBFOLDER="hunyuan3d-dit-v2-1"
TEXGEN_MODEL_PATH="tencent/Hunyuan3D-2.1"
PORT=443
HOST="0.0.0.0"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            PORT="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --model_path)
            MODEL_PATH="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --port PORT          Port to run on (default: 443)"
            echo "  --host HOST          Host to bind to (default: 0.0.0.0)"
            echo "  --model_path PATH    Model path (default: tencent/Hunyuan3D-2.1)"
            echo "  --help, -h           Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                           # Start with defaults (HTTPS on port 443)"
            echo "  $0 --port 8443              # Start on custom port"
            echo "  $0 --host localhost          # Bind to localhost only"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "📋 Configuration:"
echo "   Model Path: $MODEL_PATH"
echo "   Subfolder: $SUBFOLDER"
echo "   Texture Model: $TEXGEN_MODEL_PATH"
echo "   Host: $HOST"
echo "   Port: $PORT"
echo "   Protocol: HTTPS (Using Let's Encrypt certificate)"
echo "   SSL Certificate: $SSL_CERT"
echo "   SSL Key: $SSL_KEY"
echo ""

echo "🔐 Starting with Let's Encrypt SSL certificate..."
echo "   Access the service at: https://fast3d.angel-lab.org:$PORT"
echo ""

# Start the server with Let's Encrypt certificates
python3 gradio_app_lazy.py \
    --model_path "$MODEL_PATH" \
    --subfolder "$SUBFOLDER" \
    --texgen_model_path "$TEXGEN_MODEL_PATH" \
    --port $PORT \
    --host "$HOST" \
    --ssl \
    --ssl-cert "$SSL_CERT" \
    --ssl-key "$SSL_KEY" \
    --low_vram_mode

echo ""
echo "🔴 Server stopped."