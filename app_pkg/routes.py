from app_pkg import application
from flask import render_template, request, jsonify
import json, ipaddress, os, logging, psutil
from init_services import services, task_manager, download_queue
import pandas as pd
from datetime import datetime

logger = logging.getLogger('__main__')

@application.route('/')
@application.route('/index')
@application.route('/tasks')
def tasks():    
    return render_template('tasks.html')

@application.route('/config')
def config():

    return render_template('config.html')

@application.route('/get_tasks_table')
def get_tasks_table():
        
    data = task_manager.get_tasks_table()
    

    return {"data": data}

@application.route('/get_client_id')
def get_client_id():

    try:
        with open(os.path.join("data", "client.json"), "r") as jsonfile:        
            client_id = json.load(jsonfile)["client_id"]

        data = {
            "client_id": client_id
        }
    except:
        data = {
            "client_id": "Not available - contact support"
        }

    return data


@application.route('/get_mirror_mode')
def get_mirror_mode():

    with open(os.path.join("data", "local.json"), "r") as jsonfile:        
        mirror_mode = json.load(jsonfile)["mirror_mode"]

    data = {
        "mirror_mode": mirror_mode
    }

    return data

@application.route('/toggle_mirror_mode')
def toggle_mirror_mode():

    with open(os.path.join("data", "local.json"), "r") as jsonfile:        
        config = json.load(jsonfile)

    config["mirror_mode"] = not config["mirror_mode"]

    with open(os.path.join("data", "local.json"), "w") as jsonfile:         
        json.dump(config, jsonfile, indent = 2)

    data = {
        "mirror_mode": config["mirror_mode"]
    }

    return data

@application.route('/get_local_device')
def get_local_device():

    with open(os.path.join("data", "local.json"), "r") as jsonfile:        
        ae_title = json.load(jsonfile)['ae_title']
    
    # Get the IP address for each network interface available
    interfaces = psutil.net_if_addrs()
    ips = []
    [[ips.append(item.address) for item in interface if item.family.name == 'AF_INET' and not item.address == '127.0.0.1'] for interface in interfaces.values()]
    address = '/'.join(ips)
    device = {'ae_title': ae_title, 'address': address, 'port':11113}

    data = {
        "data": device
    }

    return data

@application.route('/manage_local_device', methods=['GET', 'POST'])
def manage_local_device():    
    
    with open(os.path.join("data", "local.json"), "r") as jsonfile:        
        config = json.load(jsonfile)
    
    config["ae_title"] = request.json["ae_title"]     
    
    # Edit device in config file
    try:
        with open(os.path.join("data", "local.json"), "w") as jsonfile:     
            json.dump(config, jsonfile, indent = 2)
    except:
        logger.error('configuration file could not be read')
        return jsonify(message = 'configuration file could not be read'), 500
    
    # Restart DICOM interfaces
    services['store_scp'].restart(request.json["ae_title"]  )
    services['store_scu'].ae_title = request.json["ae_title"]  
            
    return {"message":"Local device was updated successfully"}  

@application.route('/get_remote_devices')
def get_remote_devices():

    with open(os.path.join("data", "peers.json"), "r") as jsonfile:         
        devices = json.load(jsonfile)    

    devices = [{"name":key, 
                "ae_title":value["ae_title"],
                "address":value["address"] + ":" + str(value["port"]),
                "is_destination":value["is_destination"]} 
               for key,value in devices.items()]

    data = {
        "data": devices
    }

    return data


@application.route('/manage_remote_devices', methods=['GET', 'POST'])
def manage_remote_devices():
    
    with open(os.path.join("data", "peers.json"), "r") as jsonfile:         
        devices = json.load(jsonfile)    
    
    action = request.json["action"]
    device_name = request.json["name"]

    # Check if device already exists        
    device_exists = device_name in devices
    if action == "delete":

        if not device_exists: return jsonify(message = 'Error: el dispositivo no existe'), 500

        # Delete device from config file
        del devices[device_name]
        with open(os.path.join("data", "peers.json"), "w") as jsonfile:         
                json.dump(devices, jsonfile, indent = 2)

        return {"message":"The device has been deleted successfully"}
    
    # Check if AE title already exists
    ae_title = request.json["ae_title"]

    # Check if IP is formatted correctly
    address = request.json["address"]
    try:
        ipaddress.ip_address(address)
    except ValueError:
        return jsonify(message = 'IP address is not formatted correctly'), 500
    
    # Check port
    port = request.json["port"]
    try:
        assert port.isnumeric()
        port = int(port)
    except:
        return jsonify(message = 'port number is invalid'), 500
        
    is_destination = request.json["is_destination"]

    device = {"ae_title": ae_title, 
              "address": address, 
              "port": port, 
              "is_destination": is_destination}
    
    # Add new device
    if action == "add":
        
        if device_exists: return jsonify(message = 'This device already exists'), 500

        # Add device to config file
        devices[device_name] = device
        with open(os.path.join("data", "peers.json"), "w") as jsonfile:
                json.dump(devices, jsonfile, indent = 2)     
        
        return {"message":"The device has been added successfully"}  

    # Edit device
    elif action == "edit":
        # Check if device exists
        if not device_exists: return jsonify(message = 'The device does not exist'), 500
        
        # Edit device in config file
        devices[device_name].update(device)
        with open(os.path.join("data", "peers.json"), "w") as jsonfile:      
                json.dump(devices, jsonfile, indent = 2)

        return {"message":"The device has been update successfully"}   
    
@application.route('/dashboard')
def dashboard():

    return render_template('dashboard.html')

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
        if service_name == 'Dicom Listener':
            try:
                with open(os.path.join("data", "local.json"), "r") as jsonfile:         
                    ae_title = json.load(jsonfile)['ae_title']
                result = services[service_name].start(ae_title)
            except:
                result = 'Dicom listener AE Title could not be read from configuration file'
        else:
            result = services[service_name].start()
    
    elif action == 'stop':
        result = services[service_name].stop()
        print(result)

    return {"result": result}

# Route for server interaction
@application.route('/process_ready', methods=['GET', 'POST'])
def process_ready():

    """"

     The server uses this route to signal the completion of a processing task

    """

    # Pass the task_id to the downloader to extract the results   
    try: 
        download_queue.put(request.json['task_id'])
        logger.info(request.json['task_id'] + " put in the download_queue")
        return jsonify(message = 'Acknowledge'), 200    
    except:
        logger.error("request.json['task_id'] couldn't be read")
        return jsonify(message = 'Missing task_id in request json'), 500    


@application.route('/logs')
def logs():    
    
    return render_template('logs.html')

@application.route('/get_modules_names')
def get_modules_names():

    modules = ['client_side_app',
               'routes',
               'init_services',
               'server_monitor',
               'task_manager',
               'store_scp',               
               'compilator',
               'packer',
               'uploader_vpn',
               'downloader_queue',
               'unpacker',
               'store_scu']
    
    return {'data': modules}

@application.route('/get_logs', methods = ['GET','POST'])
def get_logs():

    if not request.json['ignore']:
        df = pd.read_csv(os.environ['LOGGING_FILE'], sep=';', names = ['datetime','level','module','function','message'])
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