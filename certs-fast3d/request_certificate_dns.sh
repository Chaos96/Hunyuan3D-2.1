#!/bin/bash

# Let's Encrypt SSL Certificate Request Script (DNS-01 Validation)
# Domain: fast3d.angel-lab.org
# This method doesn't require port 80 or 443 to be open

DOMAIN="fast3d.angel-lab.org"
EMAIL="tim@angel-lab.org"  # Change this to your email
CERT_DIR="/home/ubuntu/project/Hunyuan3D-2.1/certs-fast3d"

echo "====================================="
echo "Let's Encrypt SSL Certificate Request (DNS Validation)"
echo "Domain: $DOMAIN"
echo "====================================="

# Check if certbot is installed
if ! command -v certbot &> /dev/null; then
    echo "Certbot not found. Installing..."
    sudo apt-get update
    sudo apt-get install -y certbot
fi

echo ""
echo "This script uses DNS-01 validation. You'll need to:"
echo "1. Add a TXT record to your DNS (Cloudflare)"
echo "2. Wait for DNS propagation"
echo "3. Continue the process"
echo ""

# Request certificate using DNS validation
echo "Starting certificate request..."
sudo certbot certonly \
    --manual \
    --preferred-challenges dns \
    --agree-tos \
    --email $EMAIL \
    --domains $DOMAIN \
    -d $DOMAIN

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

    echo "✓ Certificates copied to $CERT_DIR"
    echo ""
    echo "Certificate files:"
    echo "  - Full chain: $CERT_DIR/fullchain.pem"
    echo "  - Private key: $CERT_DIR/privkey.pem"
else
    echo "✗ Failed to obtain certificate"
    exit 1
fi