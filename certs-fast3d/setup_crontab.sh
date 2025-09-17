#!/bin/bash

# Setup Crontab for Monthly Certificate Renewal
# This script adds a cron job to run the auto renewal script monthly

SCRIPT_PATH="/home/ubuntu/project/Hunyuan3D-2.1/certs-fast3d/auto_renew_and_restart.sh"

echo "Setting up crontab for automatic certificate renewal..."

# Check if the renewal script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Error: Renewal script not found at $SCRIPT_PATH"
    exit 1
fi

# Create the cron entry
# Run at 3:00 AM on the 1st of each month
CRON_ENTRY="0 3 1 * * $SCRIPT_PATH >> /home/ubuntu/project/Hunyuan3D-2.1/certs-fast3d/cron_execution.log 2>&1"

# Note: We need to use sudo/root crontab since the script requires sudo for Docker commands
echo "Note: This script needs to be added to root's crontab since it uses Docker commands."
echo ""

# Check if cron entry already exists in root's crontab
(sudo crontab -l 2>/dev/null | grep -F "$SCRIPT_PATH") > /dev/null
if [ $? -eq 0 ]; then
    echo "Cron job already exists in root's crontab. Updating..."
    # Remove old entry and add new one
    (sudo crontab -l 2>/dev/null | grep -v -F "$SCRIPT_PATH"; echo "$CRON_ENTRY") | sudo crontab -
else
    echo "Adding new cron job to root's crontab..."
    # Add new entry
    (sudo crontab -l 2>/dev/null; echo "$CRON_ENTRY") | sudo crontab -
fi

echo "Cron job installed successfully!"
echo ""
echo "The renewal script will run:"
echo "  - Time: 3:00 AM"
echo "  - Frequency: 1st day of each month"
echo "  - Script: $SCRIPT_PATH"
echo "  - Logs: /home/ubuntu/project/Hunyuan3D-2.1/certs-fast3d/auto_renewal.log"
echo "  - Cron logs: /home/ubuntu/project/Hunyuan3D-2.1/certs-fast3d/cron_execution.log"
echo ""
echo "To view current crontab: sudo crontab -l"
echo "To manually test the script: sudo $SCRIPT_PATH"
echo "To remove the cron job: sudo crontab -l | grep -v '$SCRIPT_PATH' | sudo crontab -"
echo ""
echo "Alternative cron schedules you can use:"
echo "  - Weekly (Sundays at 3 AM): 0 3 * * 0"
echo "  - Bi-weekly (1st and 15th at 3 AM): 0 3 1,15 * *"
echo "  - Daily at 3 AM: 0 3 * * *"