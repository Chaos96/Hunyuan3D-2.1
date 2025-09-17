# Hunyuan 3D is licensed under the TENCENT HUNYUAN NON-COMMERCIAL LICENSE AGREEMENT
# except for the third-party components listed below.
# Hunyuan 3D does not impose any additional limitations beyond what is outlined
# in the repsective licenses of these third-party components.
# Users must comply with all terms and conditions of original licenses of these third-party
# components and must ensure that the usage of the third party components adheres to
# all relevant laws and regulations.

# For avoidance of doubts, Hunyuan 3D means the large language models and
# their software and algorithms, including trained model weights, parameters (including
# optimizer states), machine-learning model code, inference-enabling code, training-enabling code,
# fine-tuning enabling code and other elements of the foregoing made publicly available
# by Tencent in accordance with TENCENT HUNYUAN COMMUNITY LICENSE AGREEMENT.

# Apply torchvision compatibility fix before other imports

import sys
sys.path.insert(0, './hy3dshape')
sys.path.insert(0, './hy3dpaint')


try:
    from torchvision_fix import apply_fix
    apply_fix()
except ImportError:
    print("Warning: torchvision_fix module not found, proceeding without compatibility fix")
except Exception as e:
    print(f"Warning: Failed to apply torchvision fix: {e}")


import os
import random
import shutil
import subprocess
import time
from glob import glob
from pathlib import Path

import gradio as gr

# === Lazy load + model controls injection ===
MODEL_READY = False

# Global model references - initialized as None for lazy loading
rmbg_worker = None
i23d_worker = None
floater_remove_worker = None
degenerate_face_remove_worker = None
face_reduce_worker = None
tex_pipeline = None
t2i_worker = None

def get_gpu_memory_info():
    """Get current GPU memory usage information."""
    if not torch.cuda.is_available():
        return "GPU not available", 0, 0

    try:
        torch.cuda.synchronize()
        allocated = torch.cuda.memory_allocated() / 1024**3  # GB
        reserved = torch.cuda.memory_reserved() / 1024**3    # GB
        total = torch.cuda.get_device_properties(0).total_memory / 1024**3  # GB

        return f"GPU Memory: {allocated:.1f}GB allocated, {reserved:.1f}GB reserved, {total:.1f}GB total", allocated, total
    except Exception as e:
        return f"Error getting GPU info: {str(e)}", 0, 0

def _lazy_load_if_needed(progress=gr.Progress(track_tqdm=True)):
    """Ensure heavy models are loaded only on demand, with visible progress."""
    global MODEL_READY, rmbg_worker, i23d_worker, floater_remove_worker
    global degenerate_face_remove_worker, face_reduce_worker, tex_pipeline, t2i_worker

    if MODEL_READY:
        progress(1.0, desc="✅ Models already loaded")
        memory_info, _, _ = get_gpu_memory_info()
        return True, memory_info

    try:
        # Stage 1: Initialize CUDA context
        progress(0.05, desc="🚀 Initializing CUDA context...")
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            _ = torch.rand((1, 1), device="cuda") * 0.0
            torch.cuda.synchronize()

        # Stage 2: Load background removal model
        progress(0.15, desc="📷 Loading background removal model...")
        from hy3dshape.rembg import BackgroundRemover
        rmbg_worker = BackgroundRemover()

        # Stage 3: Load main 3D generation pipeline
        progress(0.35, desc="🎨 Loading 3D generation pipeline...")
        from hy3dshape import Hunyuan3DDiTFlowMatchingPipeline
        i23d_worker = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
            args.model_path,
            subfolder=args.subfolder,
            use_safetensors=False,
            device=args.device,
        )
        if args.enable_flashvdm:
            mc_algo = 'mc' if args.device in ['cpu', 'mps'] else args.mc_algo
            i23d_worker.enable_flashvdm(mc_algo=mc_algo)
        if args.compile:
            i23d_worker.compile()

        # Stage 4: Load mesh processing workers
        progress(0.55, desc="🔧 Loading mesh processing tools...")
        from hy3dshape import FaceReducer, FloaterRemover, DegenerateFaceRemover
        floater_remove_worker = FloaterRemover()
        degenerate_face_remove_worker = DegenerateFaceRemover()
        face_reduce_worker = FaceReducer()

        # Stage 5: Load texture generation pipeline if enabled
        if HAS_TEXTUREGEN:
            progress(0.75, desc="🎯 Loading texture generation pipeline...")
            from hy3dpaint.textureGenPipeline import Hunyuan3DPaintPipeline, Hunyuan3DPaintConfig
            conf = Hunyuan3DPaintConfig(max_num_view=8, resolution=768)
            conf.realesrgan_ckpt_path = "hy3dpaint/ckpt/RealESRGAN_x4plus.pth"
            conf.multiview_cfg_path = "hy3dpaint/cfgs/hunyuan-paint-pbr.yaml"
            conf.custom_pipeline = "hy3dpaint/hunyuanpaintpbr"
            tex_pipeline = Hunyuan3DPaintPipeline(conf)

        # Stage 6: Load text-to-image pipeline if enabled
        if HAS_T2I and args.enable_t23d:
            progress(0.90, desc="📝 Loading text-to-image pipeline...")
            from hy3dgen.text2image import HunyuanDiTPipeline
            t2i_worker = HunyuanDiTPipeline('Tencent-Hunyuan/HunyuanDiT-v1.1-Diffusers-Distilled')

        progress(0.95, desc="🔥 Finalizing model setup...")
        if args.low_vram_mode:
            torch.cuda.empty_cache()

        MODEL_READY = True
        progress(1.0, desc="✅ All models loaded successfully!")

        memory_info, _, _ = get_gpu_memory_info()
        return True, memory_info

    except Exception as e:
        MODEL_READY = False
        progress(1.0, desc=f"❌ Error loading models: {str(e)}")
        print(f"[LazyLoad] error: {e}")
        import traceback
        traceback.print_exc()
        raise

def _unload_models_handler(progress=gr.Progress(track_tqdm=True)):
    """Release GPU memory and mark model as unloaded."""
    global MODEL_READY, rmbg_worker, i23d_worker, floater_remove_worker
    global degenerate_face_remove_worker, face_reduce_worker, tex_pipeline, t2i_worker

    import gc
    progress(0.1, desc="🗑️ Releasing model references...")

    # Clear all global model references
    rmbg_worker = None
    i23d_worker = None
    floater_remove_worker = None
    degenerate_face_remove_worker = None
    face_reduce_worker = None
    tex_pipeline = None
    t2i_worker = None

    progress(0.4, desc="🧹 Running garbage collection...")
    # Clear any cached variables that might hold model references
    for name in list(globals().keys()):
        if name.startswith(("_cached_", "_PIPE_", "pipe_", "model_", "renderer_", "pipeline_")):
            globals()[name] = None

    gc.collect()

    if torch.cuda.is_available():
        progress(0.7, desc="💾 Emptying CUDA cache...")
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()

    MODEL_READY = False
    progress(1.0, desc="✅ Models unloaded successfully")

    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    memory_info, _, _ = get_gpu_memory_info()
    return f"**Status:** 🔴 Models unloaded at {ts}\n\n{memory_info}"

def _load_models_handler(progress=gr.Progress(track_tqdm=True)):
    """Load models with progress tracking and memory monitoring."""
    try:
        success, memory_info = _lazy_load_if_needed(progress)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        return f"**Status:** 🟢 Models loaded at {ts}\n\n{memory_info}"
    except Exception as e:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        return f"**Status:** 🔴 Failed to load models at {ts}\n\n❌ Error: {str(e)}"

def _get_memory_status():
    """Get current memory status for display."""
    memory_info, allocated, total = get_gpu_memory_info()
    if MODEL_READY:
        status = "🟢 Models Loaded"
    else:
        status = "🔴 Models Not Loaded"

    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    return f"**Status:** {status}\n\n{memory_info}\n\n*Last updated: {ts}*"

def shape_generation_with_load(*args, progress=gr.Progress(track_tqdm=True), **kwargs):
    """Wrapper that ensures models are loaded before shape generation."""
    if not MODEL_READY:
        progress(0.0, desc="🔄 Loading models first...")
        _lazy_load_if_needed(progress)
    return shape_generation(*args, **kwargs)

def generation_all_with_load(*args, progress=gr.Progress(track_tqdm=True), **kwargs):
    """Wrapper that ensures models are loaded before full generation."""
    if not MODEL_READY:
        progress(0.0, desc="🔄 Loading models first...")
        _lazy_load_if_needed(progress)
    return generation_all(*args, **kwargs)
# === End injection ===
import torch
import trimesh
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uuid
import numpy as np

from hy3dshape.utils import logger
from hy3dpaint.convert_utils import create_glb_with_pbr_materials


MAX_SEED = 1e7
ENV = "Local" # "Huggingface"
if ENV == 'Huggingface':
    """
    Setup environment for running on Huggingface platform.

    This block performs the following:
    - Changes directory to the differentiable renderer folder and runs a shell 
        script to compile the mesh painter.
    - Installs a custom rasterizer wheel package via pip.

    Note:
        This setup assumes the script is running in the Huggingface environment 
        with the specified directory structure.
    """
    import os, spaces, subprocess, sys, shlex
    print("cd /home/user/app/hy3dgen/texgen/differentiable_renderer/ && bash compile_mesh_painter.sh")
    os.system("cd /home/user/app/hy3dgen/texgen/differentiable_renderer/ && bash compile_mesh_painter.sh")
    print('install custom')
    subprocess.run(shlex.split("pip install custom_rasterizer-0.1-cp310-cp310-linux_x86_64.whl"),
                   check=True)
else:
    """
    Define a dummy `spaces` module with a GPU decorator class for local environment.

    The GPU decorator is a no-op that simply returns the decorated function unchanged.
    This allows code that uses the `spaces.GPU` decorator to run without modification locally.
    """
    class spaces:
        class GPU:
            def __init__(self, duration=60):
                self.duration = duration
            def __call__(self, func):
                return func 

def get_example_img_list():
    """
    Load and return a sorted list of example image file paths.

    Searches recursively for PNG images under the './assets/example_images/' directory.

    Returns:
        list[str]: Sorted list of file paths to example PNG images.
    """
    print('Loading example img list ...')
    return sorted(glob('./assets/example_images/**/*.png', recursive=True))


def get_example_txt_list():
    """
    Load and return a list of example text prompts.

    Reads lines from the './assets/example_prompts.txt' file, stripping whitespace.

    Returns:
        list[str]: List of example text prompts.
    """
    print('Loading example txt list ...')
    txt_list = list()
    for line in open('./assets/example_prompts.txt', encoding='utf-8'):
        txt_list.append(line.strip())
    return txt_list


def gen_save_folder(max_size=200):
    """
    Generate a new save folder inside SAVE_DIR, maintaining a maximum number of folders.

    If the number of existing folders in SAVE_DIR exceeds `max_size`, the oldest folder is removed.

    Args:
        max_size (int, optional): Maximum number of folders to keep in SAVE_DIR. Defaults to 200.

    Returns:
        str: Path to the newly created save folder.
    """
    os.makedirs(SAVE_DIR, exist_ok=True)
    dirs = [f for f in Path(SAVE_DIR).iterdir() if f.is_dir()]
    if len(dirs) >= max_size:
        oldest_dir = min(dirs, key=lambda x: x.stat().st_ctime)
        shutil.rmtree(oldest_dir)
        print(f"Removed the oldest folder: {oldest_dir}")
    new_folder = os.path.join(SAVE_DIR, str(uuid.uuid4()))
    os.makedirs(new_folder, exist_ok=True)
    print(f"Created new folder: {new_folder}")
    return new_folder


# Removed complex PBR conversion functions - using simple trimesh-based conversion
def export_mesh(mesh, save_folder, textured=False, type='glb'):
    """
    Export a mesh to a file in the specified folder, optionally including textures.

    Args:
        mesh (trimesh.Trimesh): The mesh object to export.
        save_folder (str): Directory path where the mesh file will be saved.
        textured (bool, optional): Whether to include textures/normals in the export. Defaults to False.
        type (str, optional): File format to export ('glb' or 'obj' supported). Defaults to 'glb'.

    Returns:
        str: The full path to the exported mesh file.
    """
    if textured:
        path = os.path.join(save_folder, f'textured_mesh.{type}')
    else:
        path = os.path.join(save_folder, f'white_mesh.{type}')
    if type not in ['glb', 'obj']:
        mesh.export(path)
    else:
        mesh.export(path, include_normals=textured)
    return path




def quick_convert_with_obj2gltf(obj_path: str, glb_path: str) -> bool:
    # 执行转换
    textures = {
        'albedo': obj_path.replace('.obj', '.jpg'),
        'metallic': obj_path.replace('.obj', '_metallic.jpg'),
        'roughness': obj_path.replace('.obj', '_roughness.jpg')
        }
    create_glb_with_pbr_materials(obj_path, textures, glb_path)
            


def randomize_seed_fn(seed: int, randomize_seed: bool) -> int:
    if randomize_seed:
        seed = random.randint(0, MAX_SEED)
    return seed


def build_model_viewer_html(save_folder, height=660, width=790, textured=False):
    # Remove first folder from path to make relative path
    if textured:
        related_path = f"./textured_mesh.glb"
        template_name = './assets/modelviewer-textured-template-secure.html'
        output_html_path = os.path.join(save_folder, f'textured_mesh.html')
    else:
        related_path = f"./white_mesh.glb"
        template_name = './assets/modelviewer-template-secure.html'
        output_html_path = os.path.join(save_folder, f'white_mesh.html')
    offset = 50 if textured else 10
    with open(os.path.join(CURRENT_DIR, template_name), 'r', encoding='utf-8') as f:
        template_html = f.read()

    # Add security headers and HTTPS compatibility fixes
    security_headers = '''
    <meta http-equiv="Content-Security-Policy" content="default-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net data: blob:; frame-ancestors 'self';">
    <meta http-equiv="X-Frame-Options" content="SAMEORIGIN">
    <meta name="referrer" content="no-referrer">
    '''

    # Insert security headers after <head> tag
    template_html = template_html.replace('<head>', f'<head>\n{security_headers}')

    # Fix environment image paths for HTTPS compatibility
    template_html = template_html.replace('"/static/env_maps/', '"/static/env_maps/')
    template_html = template_html.replace("'/static/env_maps/", "'/static/env_maps/")

    with open(output_html_path, 'w', encoding='utf-8') as f:
        template_html = template_html.replace('#height#', f'{height - offset}')
        template_html = template_html.replace('#width#', f'{width}')
        # Fix potential double slashes in src path
        clean_path = related_path.rstrip('/')
        template_html = template_html.replace('#src#', clean_path)
        f.write(template_html)

    rel_path = os.path.relpath(output_html_path, SAVE_DIR)

    # Enhanced iframe with security attributes and HTTPS compatibility
    # Detect protocol for proper URL generation
    import inspect
    frame = inspect.currentframe()
    try:
        # Try to get the current request context if available
        protocol = "https" if hasattr(args, 'ssl') and args.ssl else "http"
    except:
        protocol = "http"
    finally:
        del frame

    iframe_tag = f'''
    <iframe
        src="/static/{rel_path}"
        height="{height}"
        width="100%"
        frameborder="0"
        loading="lazy"
        allow="fullscreen; xr-spatial-tracking"
        sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
        referrerpolicy="no-referrer"
        style="border: 1px solid #ddd; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
        <p>Your browser does not support iframes. Please <a href="/static/{rel_path}" target="_blank">click here</a> to view the 3D model.</p>
    </iframe>
    '''

    print(f'Find html file {output_html_path}, \
{os.path.exists(output_html_path)}, relative HTML path is /static/{rel_path}')

    return f"""
        <div style='height: {height}px; width: 100%; position: relative;'>
            {iframe_tag}
        </div>
    """

@spaces.GPU(duration=60)
def _gen_shape(
    caption=None,
    image=None,
    mv_image_front=None,
    mv_image_back=None,
    mv_image_left=None,
    mv_image_right=None,
    steps=50,
    guidance_scale=7.5,
    seed=1234,
    octree_resolution=256,
    check_box_rembg=False,
    num_chunks=200000,
    randomize_seed: bool = False,
):
    if not MV_MODE and image is None and caption is None:
        raise gr.Error("Please provide either a caption or an image.")
    if MV_MODE:
        if mv_image_front is None and mv_image_back is None \
            and mv_image_left is None and mv_image_right is None:
            raise gr.Error("Please provide at least one view image.")
        image = {}
        if mv_image_front:
            image['front'] = mv_image_front
        if mv_image_back:
            image['back'] = mv_image_back
        if mv_image_left:
            image['left'] = mv_image_left
        if mv_image_right:
            image['right'] = mv_image_right

    seed = int(randomize_seed_fn(seed, randomize_seed))

    octree_resolution = int(octree_resolution)
    if caption: print('prompt is', caption)
    save_folder = gen_save_folder()
    stats = {
        'model': {
            'shapegen': f'{args.model_path}/{args.subfolder}',
            'texgen': f'{args.texgen_model_path}',
        },
        'params': {
            'caption': caption,
            'steps': steps,
            'guidance_scale': guidance_scale,
            'seed': seed,
            'octree_resolution': octree_resolution,
            'check_box_rembg': check_box_rembg,
            'num_chunks': num_chunks,
        }
    }
    time_meta = {}

    if image is None:
        start_time = time.time()
        try:
            image = t2i_worker(caption)
        except Exception as e:
            raise gr.Error(f"Text to 3D is disable. \
            Please enable it by `python gradio_app.py --enable_t23d`.")
        time_meta['text2image'] = time.time() - start_time

    # remove disk io to make responding faster, uncomment at your will.
    # image.save(os.path.join(save_folder, 'input.png'))
    if MV_MODE:
        start_time = time.time()
        for k, v in image.items():
            if check_box_rembg or v.mode == "RGB":
                img = rmbg_worker(v.convert('RGB'))
                image[k] = img
        time_meta['remove background'] = time.time() - start_time
    else:
        if check_box_rembg or image.mode == "RGB":
            start_time = time.time()
            image = rmbg_worker(image.convert('RGB'))
            time_meta['remove background'] = time.time() - start_time

    # remove disk io to make responding faster, uncomment at your will.
    # image.save(os.path.join(save_folder, 'rembg.png'))

    # image to white model
    start_time = time.time()

    generator = torch.Generator()
    generator = generator.manual_seed(int(seed))
    outputs = i23d_worker(
        image=image,
        num_inference_steps=steps,
        guidance_scale=guidance_scale,
        generator=generator,
        octree_resolution=octree_resolution,
        num_chunks=num_chunks,
        output_type='mesh'
    )
    time_meta['shape generation'] = time.time() - start_time
    logger.info("---Shape generation takes %s seconds ---" % (time.time() - start_time))

    tmp_start = time.time()
    mesh = export_to_trimesh(outputs)[0]
    time_meta['export to trimesh'] = time.time() - tmp_start

    stats['number_of_faces'] = mesh.faces.shape[0]
    stats['number_of_vertices'] = mesh.vertices.shape[0]

    stats['time'] = time_meta
    main_image = image if not MV_MODE else image['front']
    return mesh, main_image, save_folder, stats, seed

@spaces.GPU(duration=60)
def generation_all(
    caption=None,
    image=None,
    mv_image_front=None,
    mv_image_back=None,
    mv_image_left=None,
    mv_image_right=None,
    steps=50,
    guidance_scale=7.5,
    seed=1234,
    octree_resolution=256,
    check_box_rembg=False,
    num_chunks=200000,
    randomize_seed: bool = False,
):
    start_time_0 = time.time()
    mesh, image, save_folder, stats, seed = _gen_shape(
        caption,
        image,
        mv_image_front=mv_image_front,
        mv_image_back=mv_image_back,
        mv_image_left=mv_image_left,
        mv_image_right=mv_image_right,
        steps=steps,
        guidance_scale=guidance_scale,
        seed=seed,
        octree_resolution=octree_resolution,
        check_box_rembg=check_box_rembg,
        num_chunks=num_chunks,
        randomize_seed=randomize_seed,
    )
    path = export_mesh(mesh, save_folder, textured=False)
    

    print(path)
    print('='*40)

    # tmp_time = time.time()
    # mesh = floater_remove_worker(mesh)
    # mesh = degenerate_face_remove_worker(mesh)
    # logger.info("---Postprocessing takes %s seconds ---" % (time.time() - tmp_time))
    # stats['time']['postprocessing'] = time.time() - tmp_time

    tmp_time = time.time()
    mesh = face_reduce_worker(mesh)

    # path = export_mesh(mesh, save_folder, textured=False, type='glb')
    path = export_mesh(mesh, save_folder, textured=False, type='obj') # 这样操作也会 core dump

    logger.info("---Face Reduction takes %s seconds ---" % (time.time() - tmp_time))
    stats['time']['face reduction'] = time.time() - tmp_time

    tmp_time = time.time()

    text_path = os.path.join(save_folder, f'textured_mesh.obj')
    path_textured = tex_pipeline(mesh_path=path, image_path=image, output_mesh_path=text_path, save_glb=False)
        
    logger.info("---Texture Generation takes %s seconds ---" % (time.time() - tmp_time))
    stats['time']['texture generation'] = time.time() - tmp_time

    tmp_time = time.time()
    # Convert textured OBJ to GLB using obj2gltf with PBR support
    glb_path_textured = os.path.join(save_folder, 'textured_mesh.glb')
    conversion_success = quick_convert_with_obj2gltf(path_textured, glb_path_textured)

    logger.info("---Convert textured OBJ to GLB takes %s seconds ---" % (time.time() - tmp_time))
    stats['time']['convert textured OBJ to GLB'] = time.time() - tmp_time
    stats['time']['total'] = time.time() - start_time_0
    model_viewer_html_textured = build_model_viewer_html(save_folder, 
                                                         height=HTML_HEIGHT, 
                                                         width=HTML_WIDTH, textured=True)
    if args.low_vram_mode:
        torch.cuda.empty_cache()
    return (
        gr.update(value=path),
        gr.update(value=glb_path_textured),
        model_viewer_html_textured,
        stats,
        seed,
    )

@spaces.GPU(duration=60)
def shape_generation(
    caption=None,
    image=None,
    mv_image_front=None,
    mv_image_back=None,
    mv_image_left=None,
    mv_image_right=None,
    steps=50,
    guidance_scale=7.5,
    seed=1234,
    octree_resolution=256,
    check_box_rembg=False,
    num_chunks=200000,
    randomize_seed: bool = False,
):
    start_time_0 = time.time()
    mesh, image, save_folder, stats, seed = _gen_shape(
        caption,
        image,
        mv_image_front=mv_image_front,
        mv_image_back=mv_image_back,
        mv_image_left=mv_image_left,
        mv_image_right=mv_image_right,
        steps=steps,
        guidance_scale=guidance_scale,
        seed=seed,
        octree_resolution=octree_resolution,
        check_box_rembg=check_box_rembg,
        num_chunks=num_chunks,
        randomize_seed=randomize_seed,
    )
    stats['time']['total'] = time.time() - start_time_0
    mesh.metadata['extras'] = stats

    path = export_mesh(mesh, save_folder, textured=False)
    model_viewer_html = build_model_viewer_html(save_folder, height=HTML_HEIGHT, width=HTML_WIDTH)
    if args.low_vram_mode:
        torch.cuda.empty_cache()
    return (
        gr.update(value=path),
        model_viewer_html,
        stats,
        seed,
    )


def build_app():
    title = 'Hunyuan3D-2: High Resolution Textured 3D Assets Generation'
    if MV_MODE:
        title = 'Hunyuan3D-2mv: Image to 3D Generation with 1-4 Views'
    if 'mini' in args.subfolder:
        title = 'Hunyuan3D-2mini: Strong 0.6B Image to Shape Generator'

    title = 'Hunyuan-3D-2.1'
        
    if TURBO_MODE:
        title = title.replace(':', '-Turbo: Fast ')

    title_html = f"""
    <div style="font-size: 2em; font-weight: bold; text-align: center; margin-bottom: 5px">

    {title}
    </div>
    <div align="center">
    Tencent Hunyuan3D Team
    </div>
    """
    custom_css = """
    .app.svelte-wpkpf6.svelte-wpkpf6:not(.fill_width) {
        max-width: 1480px;
    }
    .mv-image button .wrap {
        font-size: 10px;
    }
    .mv-image .icon-wrap {
        width: 20px;
    }

    /* Enhanced model controls styling */
    .status-display {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 12px;
        padding: 15px;
        border: 2px solid #e1e8ed;
        font-family: 'Monaco', 'Menlo', monospace;
        font-size: 13px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin: 10px 0;
    }

    .load-button {
        background: linear-gradient(135deg, #56ab2f 0%, #a8e6cf 100%);
        border: none;
        border-radius: 10px;
        padding: 12px 20px;
        font-weight: bold;
        text-shadow: 0 1px 2px rgba(0,0,0,0.2);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        transition: all 0.3s ease;
    }

    .load-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.2);
    }

    .unload-button {
        background: linear-gradient(135deg, #ff6b6b 0%, #ffa8a8 100%);
        border: none;
        border-radius: 10px;
        padding: 12px 20px;
        font-weight: bold;
        color: white;
        text-shadow: 0 1px 2px rgba(0,0,0,0.2);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        transition: all 0.3s ease;
    }

    .unload-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.2);
    }

    .refresh-button {
        background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%);
        border: none;
        border-radius: 8px;
        padding: 8px 15px;
        font-weight: bold;
        color: white;
        text-shadow: 0 1px 2px rgba(0,0,0,0.2);
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
        margin-top: 8px;
    }

    .refresh-button:hover {
        transform: translateY(-1px);
        box-shadow: 0 3px 6px rgba(0,0,0,0.15);
    }
    """

    with gr.Blocks(theme=gr.themes.Base(), title='Hunyuan-3D-2.1', analytics_enabled=False, css=custom_css) as demo:
        gr.HTML(title_html)
        with gr.Row():
            with gr.Column(scale=1):
                with gr.Group():
                    gr.HTML("""
                    <div style="text-align: center; padding: 10px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; margin-bottom: 15px;">
                        <h3 style="color: white; margin: 0; font-size: 18px; text-shadow: 0 2px 4px rgba(0,0,0,0.3);">🤖 Model Management</h3>
                    </div>
                    """)

                    _status_md = gr.Markdown(
                        value=_get_memory_status(),
                        elem_classes="status-display"
                    )

                    with gr.Row():
                        _btn_load = gr.Button(
                            "🚀 Load Models",
                            variant="primary",
                            size="lg",
                            elem_classes="load-button"
                        )
                        _btn_unload = gr.Button(
                            "🗑️ Unload Models",
                            variant="secondary",
                            size="lg",
                            elem_classes="unload-button"
                        )

                    _btn_refresh = gr.Button(
                        "🔄 Refresh Status",
                        variant="secondary",
                        size="sm",
                        elem_classes="refresh-button"
                    )

                    _btn_load.click(fn=_load_models_handler, outputs=_status_md)
                    _btn_unload.click(fn=_unload_models_handler, outputs=_status_md)
                    _btn_refresh.click(fn=lambda: _get_memory_status(), outputs=_status_md)


        with gr.Row():
            with gr.Column(scale=3):
                with gr.Tabs(selected='tab_img_prompt') as tabs_prompt:
                    with gr.Tab('Image Prompt', id='tab_img_prompt', visible=not MV_MODE) as tab_ip:
                        image = gr.Image(label='Image', type='pil', image_mode='RGBA', height=290)
                        caption = gr.State(None)
#                    with gr.Tab('Text Prompt', id='tab_txt_prompt', visible=HAS_T2I and not MV_MODE) as tab_tp:
#                        caption = gr.Textbox(label='Text Prompt',
#                                             placeholder='HunyuanDiT will be used to generate image.',
#                                             info='Example: A 3D model of a cute cat, white background')
                    with gr.Tab('MultiView Prompt', visible=MV_MODE) as tab_mv:
                        # gr.Label('Please upload at least one front image.')
                        with gr.Row():
                            mv_image_front = gr.Image(label='Front', type='pil', image_mode='RGBA', height=140,
                                                      min_width=100, elem_classes='mv-image')
                            mv_image_back = gr.Image(label='Back', type='pil', image_mode='RGBA', height=140,
                                                     min_width=100, elem_classes='mv-image')
                        with gr.Row():
                            mv_image_left = gr.Image(label='Left', type='pil', image_mode='RGBA', height=140,
                                                     min_width=100, elem_classes='mv-image')
                            mv_image_right = gr.Image(label='Right', type='pil', image_mode='RGBA', height=140,
                                                      min_width=100, elem_classes='mv-image')

                with gr.Row():
                    btn = gr.Button(value='Gen Shape', variant='primary', min_width=100)
                    btn_all = gr.Button(value='Gen Textured Shape',
                                        variant='primary',
                                        visible=HAS_TEXTUREGEN,
                                        min_width=100)

                with gr.Group():
                    file_out = gr.File(label="File", visible=False)
                    file_out2 = gr.File(label="File", visible=False)

                with gr.Tabs(selected='tab_options' if TURBO_MODE else 'tab_export'):
                    with gr.Tab("Options", id='tab_options', visible=TURBO_MODE):
                        gen_mode = gr.Radio(
                            label='Generation Mode',
                            info='Recommendation: Turbo for most cases, \
Fast for very complex cases, Standard seldom use.',
                            choices=['Turbo', 'Fast', 'Standard'], 
                            value='Turbo')
                        decode_mode = gr.Radio(
                            label='Decoding Mode',
                            info='The resolution for exporting mesh from generated vectset',
                            choices=['Low', 'Standard', 'High'],
                            value='Standard')
                    with gr.Tab('Advanced Options', id='tab_advanced_options'):
                        with gr.Row():
                            check_box_rembg = gr.Checkbox(
                                value=True, 
                                label='Remove Background', 
                                min_width=100)
                            randomize_seed = gr.Checkbox(
                                label="Randomize seed", 
                                value=True, 
                                min_width=100)
                        seed = gr.Slider(
                            label="Seed",
                            minimum=0,
                            maximum=MAX_SEED,
                            step=1,
                            value=1234,
                            min_width=100,
                        )
                        with gr.Row():
                            num_steps = gr.Slider(maximum=100,
                                                  minimum=1,
                                                  value=5 if 'turbo' in args.subfolder else 30,
                                                  step=1, label='Inference Steps')
                            octree_resolution = gr.Slider(maximum=512, 
                                                          minimum=16, 
                                                          value=256, 
                                                          label='Octree Resolution')
                        with gr.Row():
                            cfg_scale = gr.Number(value=5.0, label='Guidance Scale', min_width=100)
                            num_chunks = gr.Slider(maximum=5000000, minimum=1000, value=8000,
                                                   label='Number of Chunks', min_width=100)
                    with gr.Tab("Export", id='tab_export'):
                        with gr.Row():
                            file_type = gr.Dropdown(label='File Type', 
                                                    choices=SUPPORTED_FORMATS,
                                                    value='glb', min_width=100)
                            reduce_face = gr.Checkbox(label='Simplify Mesh', 
                                                      value=False, min_width=100)
                            export_texture = gr.Checkbox(label='Include Texture', value=False,
                                                         visible=False, min_width=100)
                        target_face_num = gr.Slider(maximum=1000000, minimum=100, value=10000,
                                                    label='Target Face Number')
                        with gr.Row():
                            confirm_export = gr.Button(value="Transform", min_width=100)
                            file_export = gr.DownloadButton(label="Download", variant='primary',
                                                            interactive=False, min_width=100)

            with gr.Column(scale=6):
                with gr.Tabs(selected='gen_mesh_panel') as tabs_output:
                    with gr.Tab('Generated Mesh', id='gen_mesh_panel'):
                        html_gen_mesh = gr.HTML(HTML_OUTPUT_PLACEHOLDER, label='Output')
                    with gr.Tab('Exporting Mesh', id='export_mesh_panel'):
                        html_export_mesh = gr.HTML(HTML_OUTPUT_PLACEHOLDER, label='Output')
                    with gr.Tab('Mesh Statistic', id='stats_panel'):
                        stats = gr.Json({}, label='Mesh Stats')

            with gr.Column(scale=3 if MV_MODE else 2):
                with gr.Tabs(selected='tab_img_gallery') as gallery:
                    with gr.Tab('Image to 3D Gallery', 
                                id='tab_img_gallery', 
                                visible=not MV_MODE) as tab_gi:
                        with gr.Row():
                            gr.Examples(examples=example_is, inputs=[image],
                                        label=None, examples_per_page=18)

        tab_ip.select(fn=lambda: gr.update(selected='tab_img_gallery'), outputs=gallery)
        #if HAS_T2I:
        #    tab_tp.select(fn=lambda: gr.update(selected='tab_txt_gallery'), outputs=gallery)

        btn.click(
            shape_generation_with_load,
            inputs=[
                caption,
                image,
                mv_image_front,
                mv_image_back,
                mv_image_left,
                mv_image_right,
                num_steps,
                cfg_scale,
                seed,
                octree_resolution,
                check_box_rembg,
                num_chunks,
                randomize_seed,
            ],
            outputs=[file_out, html_gen_mesh, stats, seed]
        ).then(
            lambda: (gr.update(visible=False, value=False), gr.update(interactive=True), gr.update(interactive=True),
                     gr.update(interactive=False)),
            outputs=[export_texture, reduce_face, confirm_export, file_export],
        ).then(
            lambda: gr.update(selected='gen_mesh_panel'),
            outputs=[tabs_output],
        )

        btn_all.click(
            generation_all_with_load,
            inputs=[
                caption,
                image,
                mv_image_front,
                mv_image_back,
                mv_image_left,
                mv_image_right,
                num_steps,
                cfg_scale,
                seed,
                octree_resolution,
                check_box_rembg,
                num_chunks,
                randomize_seed,
            ],
            outputs=[file_out, file_out2, html_gen_mesh, stats, seed]
        ).then(
            lambda: (gr.update(visible=True, value=True), gr.update(interactive=False), gr.update(interactive=True),
                     gr.update(interactive=False)),
            outputs=[export_texture, reduce_face, confirm_export, file_export],
        ).then(
            lambda: gr.update(selected='gen_mesh_panel'),
            outputs=[tabs_output],
        )

        def on_gen_mode_change(value):
            if value == 'Turbo':
                return gr.update(value=5)
            elif value == 'Fast':
                return gr.update(value=10)
            else:
                return gr.update(value=30)

        gen_mode.change(on_gen_mode_change, inputs=[gen_mode], outputs=[num_steps])

        def on_decode_mode_change(value):
            if value == 'Low':
                return gr.update(value=196)
            elif value == 'Standard':
                return gr.update(value=256)
            else:
                return gr.update(value=384)

        decode_mode.change(on_decode_mode_change, inputs=[decode_mode], 
                           outputs=[octree_resolution])

        def on_export_click(file_out, file_out2, file_type, 
                            reduce_face, export_texture, target_face_num):
            if file_out is None:
                raise gr.Error('Please generate a mesh first.')

            print(f'exporting {file_out}')
            print(f'reduce face to {target_face_num}')
            if export_texture:
                mesh = trimesh.load(file_out2)
                save_folder = gen_save_folder()
                path = export_mesh(mesh, save_folder, textured=True, type=file_type)

                # for preview
                save_folder = gen_save_folder()
                _ = export_mesh(mesh, save_folder, textured=True)
                model_viewer_html = build_model_viewer_html(save_folder, 
                                                            height=HTML_HEIGHT, 
                                                            width=HTML_WIDTH,
                                                            textured=True)
            else:
                mesh = trimesh.load(file_out)
                mesh = floater_remove_worker(mesh)
                mesh = degenerate_face_remove_worker(mesh)
                if reduce_face:
                    mesh = face_reduce_worker(mesh, target_face_num)
                save_folder = gen_save_folder()
                path = export_mesh(mesh, save_folder, textured=False, type=file_type)

                # for preview
                save_folder = gen_save_folder()
                _ = export_mesh(mesh, save_folder, textured=False)
                model_viewer_html = build_model_viewer_html(save_folder, 
                                                            height=HTML_HEIGHT, 
                                                            width=HTML_WIDTH,
                                                            textured=False)
            print(f'export to {path}')
            return model_viewer_html, gr.update(value=path, interactive=True)

        confirm_export.click(
            lambda: gr.update(selected='export_mesh_panel'),
            outputs=[tabs_output],
        ).then(
            on_export_click,
            inputs=[file_out, file_out2, file_type, reduce_face, export_texture, target_face_num],
            outputs=[html_export_mesh, file_export]
        )

    return demo


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", type=str, default='tencent/Hunyuan3D-2.1')
    parser.add_argument("--subfolder", type=str, default='hunyuan3d-dit-v2-1')
    parser.add_argument("--texgen_model_path", type=str, default='tencent/Hunyuan3D-2.1')
    parser.add_argument('--port', type=int, default=80)
    parser.add_argument('--host', type=str, default='0.0.0.0')
    parser.add_argument('--ssl', action='store_true', help='Enable HTTPS with SSL')
    parser.add_argument('--ssl-cert', type=str, default='./certs/cert.pem', help='Path to SSL certificate file')
    parser.add_argument('--ssl-key', type=str, default='./certs/key.pem', help='Path to SSL private key file')
    parser.add_argument('--auto-ssl', action='store_true', help='Generate self-signed SSL certificate automatically')
    parser.add_argument('--device', type=str, default='cuda')
    parser.add_argument('--mc_algo', type=str, default='mc')
    parser.add_argument('--cache-path', type=str, default='./save_dir')
    parser.add_argument('--enable_t23d', action='store_true')
    parser.add_argument('--disable_tex', action='store_true')
    parser.add_argument('--enable_flashvdm', action='store_true')
    parser.add_argument('--compile', action='store_true')
    parser.add_argument('--low_vram_mode', action='store_true')
    args = parser.parse_args()
    args.enable_flashvdm = False

    SAVE_DIR = args.cache_path
    os.makedirs(SAVE_DIR, exist_ok=True)

    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    MV_MODE = 'mv' in args.model_path
    TURBO_MODE = 'turbo' in args.subfolder

    HTML_HEIGHT = 690 if MV_MODE else 650
    HTML_WIDTH = 500
    HTML_OUTPUT_PLACEHOLDER = f"""
    <div style='height: {650}px; width: 100%; border-radius: 8px; border-color: #e5e7eb; border-style: solid; border-width: 1px; display: flex; justify-content: center; align-items: center;'>
      <div style='text-align: center; font-size: 16px; color: #6b7280;'>
        <p style="color: #8d8d8d;">Welcome to Hunyuan3D!</p>
        <p style="color: #8d8d8d;">No mesh here.</p>
      </div>
    </div>
    """

    INPUT_MESH_HTML = """
    <div style='height: 490px; width: 100%; border-radius: 8px; 
    border-color: #e5e7eb; order-style: solid; border-width: 1px;'>
    </div>
    """
    example_is = get_example_img_list()
    example_ts = get_example_txt_list()

    SUPPORTED_FORMATS = ['glb', 'obj', 'ply', 'stl']

    HAS_TEXTUREGEN = False
    if not args.disable_tex:
        try:
            # Apply torchvision fix before importing basicsr/RealESRGAN
            print("Applying torchvision compatibility fix for texture generation...")
            try:
                from torchvision_fix import apply_fix
                fix_result = apply_fix()
                if not fix_result:
                    print("Warning: Torchvision fix may not have been applied successfully")
            except Exception as fix_error:
                print(f"Warning: Failed to apply torchvision fix: {fix_error}")
            
            # Texture generation pipeline setup will be done during lazy loading
            # This just verifies the imports are available
            from hy3dpaint.textureGenPipeline import Hunyuan3DPaintPipeline, Hunyuan3DPaintConfig
            HAS_TEXTUREGEN = True
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error loading texture generator: {e}")
            print("Failed to load texture generator.")
            print('Please try to install requirements by following README.md')
            HAS_TEXTUREGEN = False

    # Text-to-image pipeline will be loaded on-demand if enabled
    HAS_T2I = args.enable_t23d

    # Import required modules but don't initialize models at startup
    # Models will be loaded on-demand via the lazy loading mechanism
    from hy3dshape.pipelines import export_to_trimesh

    # https://discuss.huggingface.co/t/how-to-serve-an-html-file/33921/2
    # create a FastAPI app with HTTPS-compatible headers
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import Response, RedirectResponse
    from fastapi.requests import Request

    app = FastAPI()

    # Add root path redirect to /app
    @app.get("/")
    async def redirect_to_app():
        return RedirectResponse(url="/4iframe_fast3d", status_code=308)  # 308 Permanent Redirect

    # Add CORS middleware for HTTPS compatibility
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, replace with specific domains
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # Custom middleware to add security headers only
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)

        # Add security headers for iframe compatibility
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"

        # For static files served in iframes
        if request.url.path.startswith("/static/"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net data: blob:; "
                "frame-ancestors 'self'; "
                "img-src 'self' data: blob:; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net;"
            )

        return response

    # create a static directory to store the static files
    static_dir = Path(SAVE_DIR).absolute()
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir, html=True), name="static")
    shutil.copytree('./assets/env_maps', os.path.join(static_dir, 'env_maps'), dirs_exist_ok=True)

    if args.low_vram_mode:
        torch.cuda.empty_cache()
    demo = build_app()
    app = gr.mount_gradio_app(app, demo, path="/4iframe_fast3d")
    # Configure SSL and HTTPS if requested
    ssl_config = None
    if args.ssl or args.auto_ssl:
        import ssl
        import os
        from pathlib import Path

        # Auto-generate self-signed certificate if requested
        if args.auto_ssl:
            cert_dir = Path('./certs')
            cert_dir.mkdir(exist_ok=True)
            cert_file = cert_dir / 'cert.pem'
            key_file = cert_dir / 'key.pem'

            if not cert_file.exists() or not key_file.exists():
                print("🔐 Generating self-signed SSL certificate...")
                try:
                    from cryptography import x509
                    from cryptography.x509.oid import NameOID
                    from cryptography.hazmat.primitives import hashes, serialization
                    from cryptography.hazmat.primitives.asymmetric import rsa
                    import datetime

                    # Generate private key
                    key = rsa.generate_private_key(
                        public_exponent=65537,
                        key_size=2048,
                    )

                    # Create certificate
                    subject = issuer = x509.Name([
                        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
                        x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
                        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Hunyuan3D"),
                        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
                    ])

                    cert = x509.CertificateBuilder().subject_name(
                        subject
                    ).issuer_name(
                        issuer
                    ).public_key(
                        key.public_key()
                    ).serial_number(
                        x509.random_serial_number()
                    ).not_valid_before(
                        datetime.datetime.utcnow()
                    ).not_valid_after(
                        datetime.datetime.utcnow() + datetime.timedelta(days=365)
                    ).add_extension(
                        x509.SubjectAlternativeName([
                            x509.DNSName("localhost"),
                            x509.DNSName("127.0.0.1"),
                            x509.DNSName("0.0.0.0"),
                        ]),
                        critical=False,
                    ).sign(key, hashes.SHA256())

                    # Write certificate and key
                    with open(cert_file, "wb") as f:
                        f.write(cert.public_bytes(serialization.Encoding.PEM))

                    with open(key_file, "wb") as f:
                        f.write(key.private_bytes(
                            encoding=serialization.Encoding.PEM,
                            format=serialization.PrivateFormat.PKCS8,
                            encryption_algorithm=serialization.NoEncryption()
                        ))

                    print(f"✅ SSL certificate generated: {cert_file}")
                    print(f"✅ SSL private key generated: {key_file}")

                except ImportError:
                    print("⚠️  cryptography package not found. Installing it or provide your own SSL certificates.")
                    print("   Run: pip install cryptography")
                    print("   Or provide --ssl-cert and --ssl-key paths")
                    args.ssl = False
                except Exception as e:
                    print(f"❌ Failed to generate SSL certificate: {e}")
                    args.ssl = False

            args.ssl_cert = str(cert_file)
            args.ssl_key = str(key_file)
            args.ssl = True

        # Configure SSL context
        if args.ssl and os.path.exists(args.ssl_cert) and os.path.exists(args.ssl_key):
            ssl_config = {
                "ssl_certfile": args.ssl_cert,
                "ssl_keyfile": args.ssl_key,
                "ssl_version": ssl.PROTOCOL_TLS,
            }

            # Update port to 443 if using default port 80 with SSL
            if args.port == 80:
                args.port = 443
                print(f"🔐 SSL enabled, switching to port {args.port}")

            protocol = "https"
        else:
            print(f"❌ SSL certificate or key file not found: {args.ssl_cert}, {args.ssl_key}")
            ssl_config = None
            protocol = "http"
    else:
        protocol = "http"

    # Print access information
    print(f"\n🚀 Hunyuan3D Server Starting...")
    print(f"📍 Access URL: {protocol}://{args.host}:{args.port}/4iframe_fast3d")
    if args.host == '0.0.0.0':
        print(f"🌐 Public URL: {protocol}://localhost:{args.port}/4iframe_fast3d")
    print(f"🔗 Root path (/) will redirect to /4iframe_fast3d")
    if ssl_config:
        print(f"🔐 HTTPS enabled with SSL certificate")
        print(f"⚠️  Note: Self-signed certificates will show security warnings in browsers")
    print(f"\n" + "="*50)

    # Start server with or without SSL
    if ssl_config:
        uvicorn.run(app, host=args.host, port=args.port, **ssl_config)
    else:
        uvicorn.run(app, host=args.host, port=args.port)
