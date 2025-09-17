#!/bin/bash

# Automated Certificate Renewal and Service Restart Script
# This script:
# 1. Finds the running Docker container with Hunyuan3D
# 2. Stops the HTTPS service inside the container
# 3. Renews the SSL certificate
# 4. Restarts the HTTPS service with new certificates
# Schedule via crontab for monthly execution

DOMAIN="fast3d.angel-lab.org"
CERT_DIR="/home/ubuntu/project/Hunyuan3D-2.1/certs-fast3d"
LOG_FILE="$CERT_DIR/auto_renewal.log"
DAYS_BEFORE_EXPIRY=30

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_message "====================================="
log_message "Starting automated certificate renewal and restart"

# Step 1: Find running Docker container
log_message "Step 1: Finding Docker container running Hunyuan3D..."
CONTAINER_ID=$(sudo docker ps --format "table {{.ID}}\t{{.Names}}\t{{.Command}}" | grep -E "start_https|gradio_app" | awk '{print $1}' | head -1)

if [ -z "$CONTAINER_ID" ]; then
    log_message "WARNING: No running Docker container found with Hunyuan3D"
    log_message "Looking for container by image name..."
    CONTAINER_ID=$(sudo docker ps --format "table {{.ID}}\t{{.Image}}" | grep -i hunyuan | awk '{print $1}' | head -1)
fi

if [ -n "$CONTAINER_ID" ]; then
    CONTAINER_NAME=$(sudo docker inspect -f '{{.Name}}' $CONTAINER_ID | sed 's/^\///')
    log_message "Found container: $CONTAINER_NAME (ID: $CONTAINER_ID)"
else
    log_message "INFO: No Docker container found. Proceeding with certificate renewal only."
fi

# Step 2: Stop HTTPS service inside container (if found)
if [ -n "$CONTAINER_ID" ]; then
    log_message "Step 2: Stopping HTTPS service inside container..."

    # Find and kill the gradio_app_lazy.py process inside container
    sudo docker exec $CONTAINER_ID bash -c "pkill -f 'gradio_app_lazy.py' || true" 2>/dev/null

    # Give it a moment to shut down cleanly
    sleep 5

    # Force kill if still running
    sudo docker exec $CONTAINER_ID bash -c "pkill -9 -f 'gradio_app_lazy.py' || true" 2>/dev/null

    log_message "HTTPS service stopped"
else
    log_message "Step 2: Skipping - no container to stop"
fi

# Step 3: Check if renewal is needed
log_message "Step 3: Checking certificate expiry..."
if [ -f "$CERT_DIR/fullchain.pem" ]; then
    EXPIRY_DATE=$(openssl x509 -enddate -noout -in "$CERT_DIR/fullchain.pem" | cut -d= -f2)
    EXPIRY_EPOCH=$(date -d "$EXPIRY_DATE" +%s)
    CURRENT_EPOCH=$(date +%s)
    DAYS_REMAINING=$(( ($EXPIRY_EPOCH - $CURRENT_EPOCH) / 86400 ))

    log_message "Certificate expires on: $EXPIRY_DATE"
    log_message "Days remaining: $DAYS_REMAINING"

    if [ $DAYS_REMAINING -gt $DAYS_BEFORE_EXPIRY ]; then
        log_message "Certificate still valid for $DAYS_REMAINING days"
        NEEDS_RENEWAL=false
    else
        log_message "Certificate needs renewal (less than $DAYS_BEFORE_EXPIRY days remaining)"
        NEEDS_RENEWAL=true
    fi
else
    log_message "No certificate found. Will attempt to obtain new certificate."
    NEEDS_RENEWAL=true
fi

# Step 4: Renew certificate if needed
if [ "$NEEDS_RENEWAL" = true ]; then
    log_message "Step 4: Renewing certificate..."

    # Stop nginx if running (to free port 80)
    sudo systemctl stop nginx 2>/dev/null || true

    # Try different renewal methods
    RENEWAL_SUCCESS=false

    # Method 1: Try Cloudflare DNS (if credentials exist)
    if [ -f "$CERT_DIR/.cloudflare_credentials" ]; then
        log_message "Attempting renewal via Cloudflare DNS..."
        sudo certbot renew \
            --dns-cloudflare \
            --dns-cloudflare-credentials "$CERT_DIR/.cloudflare_credentials" \
            --quiet
        if [ $? -eq 0 ]; then
            RENEWAL_SUCCESS=true
            log_message "✓ Renewal successful via Cloudflare DNS"
        fi
    fi

    # Method 2: Try standalone mode (port 80)
    if [ "$RENEWAL_SUCCESS" = false ]; then
        log_message "Attempting renewal via standalone mode..."
        sudo certbot renew \
            --standalone \
            --quiet
        if [ $? -eq 0 ]; then
            RENEWAL_SUCCESS=true
            log_message "✓ Renewal successful via standalone"
        fi
    fi

    # Restart nginx if it was running
    sudo systemctl start nginx 2>/dev/null || true

    if [ "$RENEWAL_SUCCESS" = true ]; then
        # Copy renewed certificates
        log_message "Copying renewed certificates..."
        sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $CERT_DIR/fullchain.pem
        sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $CERT_DIR/privkey.pem
        sudo cp /etc/letsencrypt/live/$DOMAIN/cert.pem $CERT_DIR/cert.pem
        sudo cp /etc/letsencrypt/live/$DOMAIN/chain.pem $CERT_DIR/chain.pem

        # Set proper permissions
        sudo chown $USER:$USER $CERT_DIR/*.pem
        chmod 644 $CERT_DIR/fullchain.pem $CERT_DIR/cert.pem $CERT_DIR/chain.pem
        chmod 600 $CERT_DIR/privkey.pem

        log_message "✓ Certificates updated successfully"
    else
        log_message "✗ Certificate renewal failed!"
        # Optionally send alert
        # echo "Certificate renewal failed for $DOMAIN" | mail -s "SSL Renewal Failed" admin@example.com
    fi
else
    log_message "Step 4: Skipping renewal - certificate is still valid"
fi

# Step 5: Restart HTTPS service inside container
if [ -n "$CONTAINER_ID" ]; then
    log_message "Step 5: Restarting HTTPS service inside container..."

    # Check if start_https.sh exists in container
    sudo docker exec $CONTAINER_ID bash -c "test -f /workspace/start_https.sh || test -f /app/start_https.sh || test -f ./start_https.sh" 2>/dev/null
    if [ $? -eq 0 ]; then
        # Find the correct path and restart
        sudo docker exec -d $CONTAINER_ID bash -c "
            if [ -f /workspace/start_https.sh ]; then
                cd /workspace && ./start_https.sh
            elif [ -f /app/start_https.sh ]; then
                cd /app && ./start_https.sh
            elif [ -f ./start_https.sh ]; then
                ./start_https.sh
            fi
        " 2>/dev/null

        log_message "HTTPS service restart initiated"

        # Wait and verify the service started
        sleep 10
        sudo docker exec $CONTAINER_ID bash -c "pgrep -f 'gradio_app_lazy.py'" > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            log_message "✓ HTTPS service is running"
        else
            log_message "⚠ HTTPS service may not have started properly"
        fi
    else
        log_message "WARNING: start_https.sh not found in container"
        log_message "You may need to manually restart the service"
    fi
else
    log_message "Step 5: Skipping - no container to restart"
fi

log_message "Automated renewal and restart completed"
log_message "====================================="

# Cleanup old log entries (keep last 500 lines)
if [ -f "$LOG_FILE" ]; then
    tail -n 500 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi

exit 0