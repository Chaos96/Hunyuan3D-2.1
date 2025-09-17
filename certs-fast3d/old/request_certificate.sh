#!/bin/bash

# Let's Encrypt SSL Certificate Request Script
# Domain: fast3d.angel-lab.org

DOMAIN="fast3d.angel-lab.org"
EMAIL="tim@angel-lab.org"  # Change this to your email
WEBROOT="/home/ubuntu/project/Hunyuan3D-2.1"  # Change if needed
CERT_DIR="/home/ubuntu/project/Hunyuan3D-2.1/certs-fast3d"

echo "====================================="
echo "Let's Encrypt SSL Certificate Request"
echo "Domain: $DOMAIN"
echo "====================================="

# Check if certbot is installed
if ! command -v certbot &> /dev/null; then
    echo "Certbot not found. Installing..."
    sudo apt-get update
    sudo apt-get install -y certbot
fi

# Stop any running services on port 80 temporarily
echo "Checking for services on port 80..."
sudo lsof -i :80 | grep LISTEN

# Request certificate using standalone method (temporarily uses port 80)
echo "Requesting certificate..."
sudo certbot certonly \
    --standalone \
    --non-interactive \
    --agree-tos \
    --email $EMAIL \
    --domains $DOMAIN \
    --cert-path $CERT_DIR \
    --key-path $CERT_DIR \
    --fullchain-path $CERT_DIR \
    --chain-path $CERT_DIR

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
    echo "  - Certificate: $CERT_DIR/cert.pem"
    echo "  - Chain: $CERT_DIR/chain.pem"
    echo ""
    echo "To use with your application:"
    echo "  SSL Certificate: $CERT_DIR/fullchain.pem"
    echo "  SSL Private Key: $CERT_DIR/privkey.pem"
else
    echo "✗ Failed to obtain certificate"
    echo "Common issues:"
    echo "1. Port 80 must be accessible from internet"
    echo "2. Domain must point to this server's IP"
    echo "3. No other service should be using port 80"
    exit 1
fi

echo ""
echo "Next steps:"
echo "1. Update your application to use the new certificates"
echo "2. Set up automatic renewal with: sudo crontab -e"
echo "3. Add: 0 2 * * * $CERT_DIR/renew_certificate.sh"
