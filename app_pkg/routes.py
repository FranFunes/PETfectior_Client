from flask import render_template, request, jsonify
import ipaddress, os, logging, psutil
import pandas as pd
from datetime import datetime
from sqlalchemy.exc import OperationalError


from app_pkg import application, db
from app_pkg.db_models import Device, Task, AppConfig, FilterSettings, PetModel
from app_pkg.services import services
from app_pkg.functions.task_actions import delete_task, restart_task, retry_last_step, delete_finished, delete_failed
from app_pkg.functions.helper_funcs import ping


logger = logging.getLogger('__main__')

@application.route('/')
@application.route('/index')
@application.route('/tasks')
def tasks():    
    return render_template('tasks.html')

@application.route('/config')
def config():

    return render_template('config.html')

@application.route('/dashboard')
def dashboard():

    return render_template('dashboard.html')

@application.route('/logs')
def logs():    
    
    return render_template('logs.html')

###################################################################################
###########################           TASKS          ##############################
###################################################################################

@application.route('/get_tasks_table')
def get_tasks_table(): 
    try:
        data = [{'source':t.task_source.identifier,
                'destinations': '/'.join([dest.name for dest in t.destinations]),
                'PatientName': t.task_series.patient.PatientName,
                'StudyDate': t.task_series.study.StudyDate.strftime('%d/%m/%Y'),
                'description': t.task_series.SeriesDescription,
                'imgs': str(len(t.instances))+ '/' + str(t.expected_imgs),
                'started':t.started.strftime('%d/%m/%Y %H:%M:%S'),
                'status':t.status_msg,
                'updated': t.updated.strftime('%d/%m/%Y %H:%M:%S'),
                'task_id': t.id} for t in Task.query.all()]
    except Exception as e:
        logger.error("can't access database")
        logger.error(repr(e))
        data = []

    return {"data": data}

@application.route('/manage_tasks', methods=['GET', 'POST'])
def manage_tasks():

    action = request.json['action']
    if not action in ['delete_finished','delete_failed']:
        id = request.json['task_id']            

    if action == 'delete':
        message, code = delete_task(id)   
    elif action == 'retry_last_step':
        message, code = retry_last_step(id)   
    elif action == 'restart':
        message, code = restart_task(id)   
    elif action == 'delete_finished':
        message, code = delete_finished()   
    elif action == 'delete_failed':
        message, code = delete_failed()   

    return jsonify(message = message), code


###################################################################################
##########################           CONFIG           #############################
###################################################################################

@application.route('/get_app_config')
def get_app_config():

    try:
        c = AppConfig.query.first()
        client_id = c.client_id
        server_url = c.server_url
        mirror_mode = c.mirror_mode
        shared_path = c.shared_path        
    except Exception as e:
        logger.error("can't access config in database")
        logger.error(repr(e))     
        
    data = {
        "mirror_mode": mirror_mode,
        "server_url": server_url,
        "shared_path": shared_path,
        "client_id": client_id,
    }

    return data

@application.route('/get_local_device')
def get_local_device():

    try:
        c = AppConfig.query.first()
        ae_title = c.store_scp_aet
        port = c.store_scp_port
        address = c.ip_address
    except Exception as e:
        logger.error("can't access config in database")
        logger.error(repr(e))
    
    device = {'ae_title': ae_title, 'address': address, 'port':port}
    data = {
        "data": device
    }

    return data

@application.route('/get_pet_models')
def get_pet_models():

    try:
        models = [m.name for m in PetModel.query.all()]
        return models, 200
    except Exception as e:
        logger.error("can't access pet models in database")
        logger.error(repr(e))
        return {'message': "can't access pet models in database"}, 500    

@application.route('/manage_app_config', methods=['GET', 'POST'])
def manage_app_config():   
    try:
        c = AppConfig.query.first()
        c.client_id = request.json["client_id"]
        c.server_url = request.json["server_url"]
        c.shared_path = request.json["shared_path"]
        c.mirror_mode = request.json["mirror_mode"]
        db.session.commit()
        return {"message":"App config was updated successfully"}        
    except OperationalError as e:
        logger.error("can't access config in database")
        return jsonify(message = 'Error: database is not available'), 500     

@application.route('/manage_local_device', methods=['GET', 'POST'])
def manage_local_device():   
    try:
        c = AppConfig.query.first()
        c.store_scp_aet = request.json["ae_title"]
        c.ip_address = request.json["address"]
        c.store_scp_port = request.json.get("port", c.store_scp_port)
        db.session.commit()
        # Try to restart DICOM services with the new configuration
        services['Dicom Listener'].restart()
        services['StoreSCU'].restart()
        return {"message":"Local device was updated successfully"}        
    except OperationalError as e:
        logger.error("can't access config in database")
        return jsonify(message = 'Error: database is not available'), 500     
    except OSError as e:
        logger.error("port already in use")
        return jsonify(message = 'Error: port already in use'), 500

@application.route('/get_remote_devices')
def get_remote_devices():

    devices = [{"name":d.name, 
                "ae_title":d.ae_title,
                "address":d.address + ":" + str(d.port),
                "is_destination":d.is_destination} 
               for d in Device.query.all()]

    data = {
        "data": devices
    }

    return data


@application.route('/manage_remote_devices', methods=['GET', 'POST'])
def manage_remote_devices(): 
    
    device_name = request.json["name"]
    ae_title = request.json["ae_title"]

    # Query database for device
    try:
        d = Device.query.get(device_name)
    except OperationalError as e:
        logger.error('SQL OperationalError')
        logger.error(repr(e))
        return jsonify(message = "Error al leer la base de datos"), 500    
           
    action = request.json["action"]
    if action == "delete":
        
        # Delete device and associated filters     
        try:   
            assert d
            db.session.delete(d)
            db.session.commit()
            logger.info(f'device {d} deleted')
            return jsonify(message = "Dispositivo eliminado correctamente"), 200
        except AssertionError:
            logger.error('trying to delete unexistent device')
            return jsonify(message = "Error: el dispositivo no existe"), 500    
        except Exception as e:
            logger.error('uknown error when searching database')
            logger.error(repr(e))
            return jsonify(message = "Error al leer la base de datos"), 500    
    
    
    # Check if IP is formatted correctly
    address = request.json["address"]
    try:
        ipaddress.ip_address(address)
    except ValueError:
        logger.info('IP address not formatted properly')
        return {"message":"Error: la dirección IP no es válida"}    
    
    # Check port
    port = request.json["port"]
    try:
        assert port.isnumeric()
        port = int(port)
    except:
        logger.info('invalid port')
        return {"message":"Error: el puerto no es válido"}    
            
    if action == "add":
        # Add new device        
        if d:
            logger.error('trying to create an already existent device') 
            return jsonify(message = "Error: el dispositivo ya existe"), 500    
        try:
            # Add device to database
            new_d = Device(name = device_name, ae_title = ae_title, address = address, port = port, is_destination = request.json['is_destination'])
            db.session.add(new_d)
            db.session.commit()
            logger.info(f'device {new_d} created.') 
            return jsonify(message = "Dispositivo creado correctamente"), 200   
        except:
            logger.error('uknown error when creating new device')
            logger.error(repr(e))
            return jsonify(message = "Error al crear el nuevo dispositivo"), 500  
 
    # Edit device
    elif action == "edit":
        # Check if device exists
        if not d:
            logger.error('trying to edit an unexistent device') 
            return jsonify(message = "Error: el dispositivo no existe"), 500    
        
        # Edit device in database     
        try:       
            d.ae_title = ae_title
            d.address = address
            d.port = port
            d.is_destination = request.json['is_destination']
            db.session.commit()
            logger.info('device edited')
            return {"message":"Dispositivo editado correctamente"}    
        except Exception as e:
            logger.info('edit device failed')
            print(repr(e))
            return {"message":"Error al acceder a la base de datos"}

@application.route('/ping_remote_device', methods=['GET', 'POST'])
def ping_remote_device():   

    ping_result = ping(request.json['address'], count = 2)
    if ping_result:
        return jsonify(message = request.json['address'] + ' is reacheable!!!'), 200
    else:
        return jsonify(message = request.json['address'] + ' is unreacheable!!!'), 500
    
@application.route('/echo_remote_device', methods=['GET', 'POST'])
def echo_remote_device():       
    echo_response = services['Dicom Listener'].echo(request.json)
    if echo_response == 0:
        return jsonify(message = f"DICOM ECHO to {request.json['ae_title']}@{request.json['address']}:{request.json['port']} succesful"), 200
    else:
        return jsonify(message = f"DICOM ECHO to {request.json['ae_title']}@{request.json['address']}:{request.json['port']} failed"), 500

@application.route('/recon_settings', methods=['GET', 'POST'])
def recon_settings():

    if request.method == 'GET':
        try:
            # Send recon information
            recons = FilterSettings.query.all()
            recons = [{'id':r.id, 'fwhm':r.fwhm, 'description':r.description, 'series_number':r.series_number,
                       'enabled':r.enabled, 'mode':r.mode, 'model': r.model, 'noise': r.noise} for r in recons]
            return jsonify(data = recons), 200
        except Exception as e:
            logger.error(repr(e))
            return jsonify(message = "Error while querying recon settings"), 500

    elif request.method == 'POST':
                
        action = request.json["action"]
        if action == "add":
            try:
                new_rs = FilterSettings(fwhm = request.json['fwhm'], description = request.json['description'],
                                        series_number = request.json['series_number'], enabled = request.json['enabled'],
                                        mode = request.json['mode'], model = request.json['model'], noise = request.json['noise'])
                db.session.add(new_rs)
                db.session.commit()
                logger.info(f'new post filter settings {repr(new_rs)} created.') 
                return jsonify(message = "Configuración modificada exitosamente"), 200   
            except:
                logger.error('uknown error when creating new post filter settings')
                logger.error(repr(e))
                return jsonify(message = "Error al modificar la configuración"), 500
        
        # Query database for instance
        try:
            rs = FilterSettings.query.get(request.json['id'])
            assert rs
        except OperationalError as e:
            logger.error('SQL OperationalError')
            logger.error(repr(e))
            return jsonify(message = "Error al leer la base de datos"), 500    
        except AssertionError:
            logger.error('trying to delete unexistent post filter settings')
            return jsonify(message = "Error: la configuración no existe"), 500  
            
        if action == "delete":       
            try:   
                db.session.delete(rs)
                db.session.commit()
                logger.info(f'{rs} deleted')
                return jsonify(message = "Configuración modificada correctamente"), 200
            except Exception as e:
                logger.error('uknown error when searching database')
                logger.error(repr(e))
                return jsonify(message = "Error al leer la base de datos"), 500   
        
        if action == 'edit':
            try:                
                rs.fwhm = request.json['fwhm']
                rs.description = request.json['description']
                rs.enabled = request.json['enabled']  
                rs.mode = request.json['mode']
                rs.series_number = request.json['series_number']
                rs.noise = request.json['noise']
                rs.model = request.json['model']
                db.session.commit()
                logger.info(f'{rs} edited')
                return jsonify(message = "Se modificó la configuración correctamente"), 200
            except Exception as e:
                logger.error('uknown error when searching database')
                logger.error(repr(e))
                return jsonify(message = "Error al leer la base de datos"), 500
        
        else:
            return jsonify(message = "Acción desconocida"), 500


###################################################################################
###########################         PROCESSES        ##############################
###################################################################################    

@application.route('/check_server_connection')
def check_server_connection():

    data = services['Server Monitor'].get_statistics()
    data['state_duration'] = str(data['state_duration']) + ' sec'
    data['total_uptime'] = str(data['total_uptime']) + ' sec'
    data['total_downtime'] = str(data['total_downtime']) + ' sec'

    return {"data": [data]}
    

@application.route('/get_services_status')
def get_services_status():

    data = [{'service_name':name, 'status':service.get_status()} for name, service in services.items()]            

    return {"data": data}

@application.route('/manage_service', methods=['GET', 'POST'])
def manage_service():
    
    action = request.json['action']
    service_name = request.json['service_name']
    if action == 'start':
        result = services[service_name].start()    
    elif action == 'stop':
        result = services[service_name].stop()        

    return {"result": result}

###################################################################################
###########################           LOGS           ##############################
###################################################################################    

@application.route('/get_modules_names')
def get_modules_names():

    modules = ['compilator',
               'petfectior_client',
               'db_models',
               'db_store_handler',
               'downloader',
               'packer',
               'routes',
               'services',
               'server_monitor',
               'store_scp',               
               'store_scu',
               'task_actions',
               'task_manager',
               'unpacker',
               'uploader',               
               'validator',]
    
    return {'data': modules}

@application.route('/get_app_logs', methods = ['GET','POST'])
def get_app_logs():

    if not request.json['ignore']:
        df = pd.read_csv(os.path.join(os.environ['LOGGING_FILEPATH'],'output.log'), sep=';', names = ['datetime','level','module','function','message'])
        df['datetime'] = df['datetime'].map(lambda x: datetime.strptime(x,'%Y-%m-%d %H:%M:%S,%f'))

        # Filter by level
        if request.json['levels']:
            df = df[df.apply(lambda x:x.level in request.json['levels'], axis = 1)] 

        # Filter by date
        if request.json['dateSelector'] == 'range':
            start_date = pd.Timestamp(request.json['startDate'] + " " + request.json['startTime'])
            end_date = pd.Timestamp(request.json['endDate'] + " " + request.json['endTime'])
            df = df[(df['datetime'] >= start_date) & (df['datetime'] <= end_date)]

        df['date'] = df['datetime'].map(lambda x: x.strftime('%d/%m/%y'))
        df['time'] = df['datetime'].map(lambda x: x.strftime('%H:%M:%S'))            

        # Filter by module
        if request.json['process'] != 'ALL':
            df = df[df.module == request.json['process']]

        data = df.to_dict('records')
    else:
        data = []

    return {"data": data}

@application.route('/get_dicom_logs', methods = ['GET','POST'])
def get_dicom_logs():

    df = pd.read_csv(os.path.join(os.environ['LOGGING_FILEPATH'],'dicom.log'), sep=';', names = ['datetime','level','message'])
    df['timestamp'] = df['datetime'].map(lambda x: datetime.strptime(x,'%Y-%m-%d %H:%M:%S,%f'))

    # Filter by date
    if request.json['dateSelector'] == 'range':
        start_date = pd.Timestamp(request.json['startDate'] + " " + request.json['startTime'])
        end_date = pd.Timestamp(request.json['endDate'] + " " + request.json['endTime'])
        df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]  
    
    log = df.drop(['timestamp','level'], axis = 1).to_csv(index = False, header = False, sep = ';')

    return {"data": log}

###################################################################################
######################          SERVER INTERACTION           ######################
###################################################################################    

# Route for server interaction
@application.route('/process_ready', methods=['GET', 'POST'])
def process_ready():

    """"

     The server uses this route to signal the completion of a processing task

    """

    # Pass the task_id to the downloader to extract the results   
    try:
        # Flag step as completed     
        task = Task.query.get(request.json['task_id'])
        task.current_step = 'downloader'
        task.step_state = 1
        db.session.commit()
        logger.info(f"Task {task.id} processing done, downloading results.")        
        return jsonify(message = 'Acknowledge'), 200    
    except:
        logger.error("request.json['task_id'] couldn't be read")
        return jsonify(message = 'Missing task_id in request json'), 500    





