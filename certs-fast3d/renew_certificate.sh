#!/bin/bash

# Let's Encrypt SSL Certificate Auto-Renewal Script
# Domain: fast3d.angel-lab.org
# Run this via crontab for automatic renewal

DOMAIN="fast3d.angel-lab.org"
CERT_DIR="/home/ubuntu/project/Hunyuan3D-2.1/certs-fast3d"
LOG_FILE="$CERT_DIR/renewal.log"
DAYS_BEFORE_EXPIRY=30  # Renew if certificate expires in less than 30 days

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_message "====================================="
log_message "Starting certificate renewal check"
log_message "Domain: $DOMAIN"

# Check if certbot is installed
if ! command -v certbot &> /dev/null; then
    log_message "ERROR: Certbot not found. Please install certbot first."
    exit 1
fi

# Check certificate expiry
if [ -f "$CERT_DIR/fullchain.pem" ]; then
    EXPIRY_DATE=$(openssl x509 -enddate -noout -in "$CERT_DIR/fullchain.pem" | cut -d= -f2)
    EXPIRY_EPOCH=$(date -d "$EXPIRY_DATE" +%s)
    CURRENT_EPOCH=$(date +%s)
    DAYS_REMAINING=$(( ($EXPIRY_EPOCH - $CURRENT_EPOCH) / 86400 ))

    log_message "Certificate expires on: $EXPIRY_DATE"
    log_message "Days remaining: $DAYS_REMAINING"

    if [ $DAYS_REMAINING -gt $DAYS_BEFORE_EXPIRY ]; then
        log_message "Certificate is still valid for $DAYS_REMAINING days. No renewal needed."
        exit 0
    fi
else
    log_message "WARNING: No existing certificate found. Attempting to obtain new certificate..."
fi

# Attempt renewal
log_message "Attempting certificate renewal..."

# Try renewal with standalone mode (uses port 80)
sudo certbot renew \
    --standalone \
    --pre-hook "systemctl stop nginx 2>/dev/null || true" \
    --post-hook "systemctl start nginx 2>/dev/null || true" \
    --quiet

RENEWAL_STATUS=$?

if [ $RENEWAL_STATUS -eq 0 ]; then
    log_message "✓ Certificate renewal successful!"

    # Copy renewed certificates
    if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
        log_message "Copying renewed certificates to $CERT_DIR..."
        sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $CERT_DIR/fullchain.pem
        sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $CERT_DIR/privkey.pem
        sudo cp /etc/letsencrypt/live/$DOMAIN/cert.pem $CERT_DIR/cert.pem
        sudo cp /etc/letsencrypt/live/$DOMAIN/chain.pem $CERT_DIR/chain.pem

        # Set proper permissions
        sudo chown $USER:$USER $CERT_DIR/*.pem
        chmod 644 $CERT_DIR/fullchain.pem $CERT_DIR/cert.pem $CERT_DIR/chain.pem
        chmod 600 $CERT_DIR/privkey.pem

        log_message "✓ Certificates copied successfully"

        # Restart services that use the certificates
        # Uncomment and modify as needed for your services
        # sudo systemctl reload nginx 2>/dev/null
        # sudo systemctl restart your-app-service 2>/dev/null

        # If using the Hunyuan3D HTTPS server
        if pgrep -f "start_https.sh" > /dev/null; then
            log_message "Detected running HTTPS server. Please restart it to use new certificates."
            # You may want to implement automatic restart here
        fi
    fi
else
    log_message "✗ Certificate renewal failed with status: $RENEWAL_STATUS"

    # Send alert (configure email/notification as needed)
    # echo "Certificate renewal failed for $DOMAIN" | mail -s "SSL Renewal Failed" admin@example.com
fi

log_message "Renewal check completed"
log_message "====================================="

# Cleanup old log entries (keep last 100 lines)
if [ -f "$LOG_FILE" ]; then
    tail -n 100 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi

exit $RENEWAL_STATUS