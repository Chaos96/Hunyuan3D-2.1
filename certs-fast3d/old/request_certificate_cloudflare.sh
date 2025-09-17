#!/bin/bash

# Let's Encrypt SSL Certificate Request Script (Cloudflare DNS Automation)
# Domain: fast3d.angel-lab.org
# Fully automated - no port requirements!

DOMAIN="fast3d.angel-lab.org"
EMAIL="tim@angel-lab.org"  # Change this to your email
CERT_DIR="/home/ubuntu/project/Hunyuan3D-2.1/certs-fast3d"

# Cloudflare API credentials (need to set these)
CF_EMAIL="your-cloudflare-email@gmail.com"  # Your Cloudflare account email
CF_API_KEY="your-cloudflare-global-api-key"  # Get from Cloudflare dashboard

echo "====================================="
echo "Let's Encrypt SSL Certificate Request"
echo "Using Cloudflare DNS (Automated)"
echo "Domain: $DOMAIN"
echo "====================================="

# Check if credentials are set
if [[ "$CF_EMAIL" == "your-cloudflare-email@gmail.com" ]] || [[ "$CF_API_KEY" == "your-cloudflare-global-api-key" ]]; then
    echo "ERROR: Please set your Cloudflare credentials in this script first!"
    echo ""
    echo "How to get Cloudflare API key:"
    echo "1. Log in to Cloudflare Dashboard"
    echo "2. Go to My Profile > API Tokens"
    echo "3. View 'Global API Key'"
    echo "4. Update CF_EMAIL and CF_API_KEY in this script"
    exit 1
fi

# Install certbot and cloudflare plugin if needed
if ! command -v certbot &> /dev/null; then
    echo "Installing certbot..."
    sudo apt-get update
    sudo apt-get install -y certbot
fi

if ! dpkg -l | grep -q python3-certbot-dns-cloudflare; then
    echo "Installing Cloudflare DNS plugin..."
    sudo apt-get install -y python3-certbot-dns-cloudflare
fi

# Create Cloudflare credentials file
CF_CREDS_FILE="$CERT_DIR/.cloudflare.ini"
cat > "$CF_CREDS_FILE" << EOF
dns_cloudflare_email = $CF_EMAIL
dns_cloudflare_api_key = $CF_API_KEY
EOF
chmod 600 "$CF_CREDS_FILE"

echo "Requesting certificate (automatic DNS validation)..."
sudo certbot certonly \
    --dns-cloudflare \
    --dns-cloudflare-credentials "$CF_CREDS_FILE" \
    --dns-cloudflare-propagation-seconds 20 \
    --non-interactive \
    --agree-tos \
    --email $EMAIL \
    --domains $DOMAIN

# Check if successful
if [ $? -eq 0 ]; then
    echo "✓ Certificate obtained successfully!"

    # Copy certificates to our directory
    echo "Copying certificates to $CERT_DIR..."
    sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $CERT_DIR/fullchain.pem
    sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $CERT_DIR/privkey.pem
    sudo cp /etc/letsencrypt/live/$DOMAIN/cert.pem $CERT_DIR/cert.pem
    sudo cp /etc/letsencrypt/live/$DOMAIN/chain.pem $CERT_DIR/chain.pem

    # Set proper permissions
    sudo chown $USER:$USER $CERT_DIR/*.pem
    chmod 644 $CERT_DIR/fullchain.pem $CERT_DIR/cert.pem $CERT_DIR/chain.pem
    chmod 600 $CERT_DIR/privkey.pem

    # Remove credentials file for security
    rm -f "$CF_CREDS_FILE"

    echo "✓ Certificates copied to $CERT_DIR"
    echo ""
    echo "To use with your HTTPS server:"
    echo "  --ssl-certfile $CERT_DIR/fullchain.pem"
    echo "  --ssl-keyfile $CERT_DIR/privkey.pem"
else
    echo "✗ Failed to obtain certificate"
    rm -f "$CF_CREDS_FILE"
    exit 1
fi