# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Hunyuan3D-2.1 is Tencent's production-ready 3D asset generation system that converts images to high-fidelity 3D models with Physically-Based Rendering (PBR) textures. The system consists of two main components:

1. **Hunyuan3D-Shape** (`hy3dshape/`) - Image-to-3D shape generation using diffusion models
2. **Hunyuan3D-Paint** (`hy3dpaint/`) - PBR texture synthesis for generated meshes

## Architecture

### Core Components

- **`hy3dshape/`** - Shape generation pipeline with DiT (Diffusion Transformer) architecture
  - `hy3dshape/pipelines/` - Main inference pipelines
  - `hy3dshape/models/` - Core model implementations
  - `hy3dshape/utils/` - Utilities for mesh processing and visualization

- **`hy3dpaint/`** - Texture synthesis pipeline with custom rasterization
  - `textureGenPipeline.py` - Main texture generation pipeline
  - `custom_rasterizer/` - CUDA-based rasterization components (requires compilation)
  - `DifferentiableRenderer/` - Custom rendering engine
  - `src/` - Training and data loading infrastructure

- **API Layer** - FastAPI-based REST API for production deployment
  - `api_server.py` - Main API server with Pydantic models
  - `api_models.py` - Request/response models
  - `model_worker.py` - Background model inference worker

### Key Files

- `gradio_app.py` - Main Gradio web interface
- `gradio_app_lazy.py` - Lazy-loading variant for lower VRAM usage
- `demo.py` - Simple command-line demo
- `constants.py` - Global configuration constants

## Development Setup

### Installation Commands

```bash
# Install PyTorch with CUDA support
pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu124

# Install Python dependencies
pip install -r requirements.txt

# Compile custom rasterizer (required for texture generation)
cd hy3dpaint/custom_rasterizer
pip install -e .
cd ../..

# Compile mesh painter (required for PBR rendering)
cd hy3dpaint/DifferentiableRenderer
bash compile_mesh_painter.sh
cd ../..

# Download RealESRGAN weights for texture upscaling
wget https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth -P hy3dpaint/ckpt
```

### Running the Application

**Gradio Web Interface:**
```bash
python3 gradio_app.py \
  --model_path tencent/Hunyuan3D-2.1 \
  --subfolder hunyuan3d-dit-v2-1 \
  --texgen_model_path tencent/Hunyuan3D-2.1 \
  --low_vram_mode
```

**API Server:**
```bash
python api_server.py
```
Access interactive documentation at:
- Swagger UI: `http://localhost:8081/docs`
- ReDoc: `http://localhost:8081/redoc`

**Simple Demo:**
```bash
python demo.py --image_path assets/demo.png
```

### Testing

**API Testing:**
```bash
python test_api_server.py
```

**Shape Generation Only:**
```bash
python hy3dshape/minimal_demo.py
python hy3dshape/minimal_demo_with_ckpt.py
```

**Texture Generation:**
```bash
python hy3dpaint/demo.py
```

## System Requirements

- **GPU Memory:** 10GB for shape generation, 21GB for textures, 29GB for both
- **Python:** 3.10+
- **CUDA:** Required for custom rasterizer compilation
- **PyTorch:** 2.5.1+ with CUDA 12.4

## Code Integration Patterns

### Using the Diffusers-like API

```python
import sys
sys.path.insert(0, './hy3dshape')
sys.path.insert(0, './hy3dpaint')

from hy3dshape.pipelines import Hunyuan3DDiTFlowMatchingPipeline
from textureGenPipeline import Hunyuan3DPaintPipeline, Hunyuan3DPaintConfig

# Shape generation
shape_pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained('tencent/Hunyuan3D-2.1')
mesh_untextured = shape_pipeline(image='path/to/image.png')[0]

# Texture generation
paint_pipeline = Hunyuan3DPaintPipeline(Hunyuan3DPaintConfig(max_num_view=6, resolution=512))
mesh_textured = paint_pipeline(mesh_path, image_path='path/to/image.png')
```

### Configuration Management

The system uses OmegaConf for configuration management. Key configuration files:
- `constants.py` - Global constants and default values
- `hy3dshape/configs/` - Shape generation configurations
- `hy3dpaint/cfgs/` - Texture generation configurations

### Model Loading

Models are loaded via Hugging Face Hub:
- Shape model: `tencent/Hunyuan3D-2.1` (subfolder: `hunyuan3d-dit-v2-1`)
- Paint model: `tencent/Hunyuan3D-2.1` (subfolder: `hunyuan3d-paintpbr-v2-1`)

## Important Notes

- The texture generation pipeline requires custom CUDA components that must be compiled
- Background removal is handled automatically via rembg
- Output formats supported: GLB, OBJ with textures
- The system supports both synchronous and asynchronous API endpoints for production use