#!/bin/bash

# Hunyuan3D HTTP Server Startup Script
# This script starts the Hunyuan3D server with regular HTTP

echo "🚀 Starting Hunyuan3D with HTTP support..."
echo "================================"

# Default arguments
MODEL_PATH="tencent/Hunyuan3D-2.1"
SUBFOLDER="hunyuan3d-dit-v2-1"
TEXGEN_MODEL_PATH="tencent/Hunyuan3D-2.1"
PORT=80
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
            echo "  --port PORT          Port to run on (default: 80)"
            echo "  --host HOST          Host to bind to (default: 0.0.0.0)"
            echo "  --model_path PATH    Model path (default: tencent/Hunyuan3D-2.1)"
            echo "  --help, -h           Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                           # Start with defaults (HTTP on port 80)"
            echo "  $0 --port 8080              # Start on custom port"
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
echo "   Protocol: HTTP"
echo ""

# Start the server
python3 gradio_app_lazy.py \
    --model_path "$MODEL_PATH" \
    --subfolder "$SUBFOLDER" \
    --texgen_model_path "$TEXGEN_MODEL_PATH" \
    --port $PORT \
    --host "$HOST" \
    --low_vram_mode

echo ""
echo "🔴 Server stopped."