import os, logging, subprocess
from app_pkg import application, db
from app_pkg.db_models import Task, AppConfig
from shutil import make_archive, unpack_archive, rmtree, copy
import numpy as np
from scipy.ndimage import gaussian_filter

# Configure logging
logger = logging.getLogger('__main__')


def process(task_id):

    with application.app_context():

        task = Task.query.get(task_id)
        config = AppConfig.query.first()
        zip_filename = os.path.join(config.shared_mount_point,'to_process',task.id + '_' + config.client_id + '.zip')        
        unzip_folder = os.path.join('temp_process',task.id)
        os.makedirs(unzip_folder, exist_ok=True)
        unpack_archive(zip_filename, unzip_folder)
        voxels_file = os.path.join(unzip_folder, 'voxels.npy')

        array = np.load(voxels_file)
        noise = np.zeros_like(array)
        noise[64:96,64:96,60:70] = array[64:96,64:96,60:70]
        array[64:96,64:96,60:70] = 0
        
        np.save(os.path.join(unzip_folder, 'denoised.npy'), array)
        np.save(os.path.join(unzip_folder, 'noise.npy'), noise)

        os.remove(voxels_file)
        archive_name = os.path.join(config.shared_mount_point,'processed',task.id + '_' + config.client_id)        
        make_archive(archive_name, 'zip', unzip_folder)

        rmtree('temp_process')
        os.remove(zip_filename)

        # Flag step as completed     
        task.current_step = 'downloader'
        task.step_state = 1
        db.session.commit()

def ping(target_host, timeout = 100, count = 3):

    if os.name == "nt":
        command = ["ping", "-w", str(timeout), "-n", str(count), target_host]
    elif os.name == "posix":
        command = ["ping", "-W", str(timeout), "-c", str(count), target_host]
    else:
        return False

    try:
        completed_process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout = completed_process.stdout
        stderr = completed_process.stderr

        if completed_process.returncode == 0:
            return True
        else:
            return False
    except subprocess.CalledProcessError as e:
        return False
    

def filter_3D(img3d, FWHM, pixel_sizes):    
    """Aplica un filtro Gaussiano 3D a una imagen 3D 
   
    Esta función toma un arreglo de voxels 3D (img3d), y los 
    filtra con un kernel Gaussiano con FWHM (el tamaño del kernel Gaussiano en XYZ en mm)
    
    Devuelve una imagen filtrada.
        
    Args:
        img3d (np.ndarray): arreglo 3D de voxels de la imagen PET 
        FWHM (float): tamaño del kernel Gaussiano en XYZ (mm)        
        pixel_sizes (np.ndarray): arreglo detres elementos con los tamaños de voxel en mm 
            
    Salidas:
        img3d (np.ndarray): imagen filtrada con un kernel Gaussiano 
                          
    Ejemplo:
        >>> filtered = filtra_3D(img3d, FWHM = 5.1, pixel_sizes = [3.64583325, 3.64583325, 3.2699999 ])
                                         
        Resultado esperado: img3d será un arreglo voxels 3D que representa a 
        la imagen PET filtrada con un kernel Gaussiano con FWHM = 5.1 mm 
   
    Autor:
        Mauro Namías (mnamias@fcdn.org.ar)
   
    Versiones:
    - 1.0.0 (5 de Julio de 2023): Versión inicial de la función.
    """
    
    if FWHM == 0:
        return img3d
    
    pad = 21
    padded  = np.pad(img3d, pad_width=pad, mode='linear_ramp')    
    
    FWHMss = np.array([FWHM, FWHM, FWHM])
    FWHMs_vox = np.divide(FWHMss, pixel_sizes)
    sigmas = FWHMs_vox/2.35
    
    filtered = gaussian_filter(padded, sigmas)               
    filtered = filtered[pad:-pad,pad:-pad,pad:-pad]            
                
    return filtered
