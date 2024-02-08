# Introducción

PETfectiorClient es una aplicación diseñada para el intercambio de objetos DICOM entre la red de un cliente y un servidor de procesamiento remoto. Su objetivo es simplificar el flujo de trabajo tanto del lado del usuario como del servidor para aquellos productos comerciales que ofrecen el procesamiento de imágenes médicas en formato SAS (Software As a Service). Este flujo de trabajo requiere que los datos de imagen sean enviados a un servidor remoto, ajeno a la institución del usuario, a través de Internet. Esto habitualmente requiere que el usuario exporte las imágenes a archivos en formato DICOM, las anonimice manualmente, y las suba al servidor a través de una interfaz web convencional. PETfectiorClient provee un flujo de trabajo automatizado para este proceso. El usuario simplemente envía las imágenes a un nodo DICOM que expone PETfectiorClient y espera que las imágenes procesadas lleguen de vuelta a su estación de trabajo. El resto del proceso, que es transparente al usuario, involucra:
- Recibir las imágenes DICOM y organizarlas en series completas;
- Registrar los datos de red necesarios para devolver las imágenes procesadas;
- Extraer los datos de pixel y los metadatos necesarios para el procesamiento, eliminando los datos identificatorios del cliente;
- Comprimir los datos y enviarlos a través de internet, esperando la respuesta del servidor
- Una vez recibida la respuesta, extraer los valores de pixeles de la imagen procesada, identificar a qué imagen corresponde y reconstruir los objetos DICOM correspondientes a ese paciente y estudio.
- Enviar por DICOM las imágenes procesadas a la estación de destino.

La aplicación provee una interfaz web que permite al usuario observar y administrar el flujo de trabajo.

# Instrucciones de instalación
La aplicación corre sobre Docker, para simplificar la gestión de las dependencias y la coordinación de los diferentes módulos que
la componen. 

## Prerequisitos
1. El dispositivo donde se instalará la aplicación debe cumplir los siguientes requisitos:
    - Ser compatible con Docker ([ver requisitos](https://docs.docker.com/engine/install/))
    - Estar conectado, a través de la red local, a los dispositivos desde los cuales se vayan a enviar imágenes para procesar (escaner, estaciones de trabajo, PACS)
    - Tener una dirección de IP fija y conocida en dicha red. Esta dirección debe apuntarse para realizar la configuración más adelante.
    - Tener conexión a internet
2. Verificar que Docker esté instalado en el dispositivo donde correrá la aplicación, tipeando *docker* en una terminal. El mensaje
de ayuda de uso de Docker debería mostrarse. Si Docker no está instalado, se pueden seguir las instrucciones de instalación y 
configuración en el sitio de Docker:
[https://docs.docker.com/engine/install/](https://docs.docker.com/engine/install/)
3. Verificar que Docker esté instalado y configurado correctamente corriendo el siguiente comando en una terminal:
*docker container run hello-world*
Si la instalación de Docker está corriendo correctamente, se mostrará el siguiente mensaje:<br>
Hello from Docker!<br>
This message shows that your installation appears to be working correctly.
4. Apuntar la dirección IP 

## Descarga del repositorio y prueba de la aplicación
1. Descargar el contenido de este repositorio desde la página de Github del mismo (Code -> Download ZIP).
2. Extraer el archivo comprimido en una carpeta.
3. En la carpeta donde se extrajeron los contenidos, existe un directorio *vpn*. Se debe crear el subdirectorio *config* dentro de *vpn*, y pegar dentro de ese directorio los archivos de autenticación solicitados al proveedor.
4. Desde un línea de comandos, navegar hasta la carpeta donde se extrajeron los contenidos (aquella con el archivo *docker-compose.yml*) y
correr el siguiente comando:<br>
*docker compose up*
5. Se mostrarán múltiples mensajes de inicialización de los diferentes módulos que componen la aplicación. Al final, deberían verse las siguientes líneas que indican que la inicialización fue correcta:<br>
petfectior-client  | 2024-02-07 18:08:01,980 - INFO in __init__ @ <module>: App config found in the database<br>
petfectior-client  | INFO  [alembic.runtime.migration] Context impl MySQLImpl.<br>
petfectior-client  | INFO  [alembic.runtime.migration] Will assume non-transactional DDL.<br>
petfectior-client  | [2024-02-07 18:08:02 +0000] [1] [INFO] Starting gunicorn 21.2.0<br>
petfectior-client  | [2024-02-07 18:08:02 +0000] [1] [INFO] Listening at: http://0.0.0.0:8000 (1)<br>
petfectior-client  | [2024-02-07 18:08:02 +0000] [1] [INFO] Using worker: sync<br>
petfectior-client  | [2024-02-07 18:08:02 +0000] [26] [INFO] Booting worker with pid: 26<br>
petfectior-client  | 2024-02-07 18:08:03,031 - INFO in __init__ @ <module>: App config found in the database<br>
petfectior-client  | 2024-02-07 18:08:03,045 - INFO in store_scp @ start: Starting Store SCP: PETFECTIOR@0.0.0.0:11115<br>
petfectior-client  | 2024-02-07 18:08:03,046 - INFO in compilator @ start: Compilator started<br>
petfectior-client  | 2024-02-07 18:08:03,048 - INFO in validator @ start: Started<br>
petfectior-client  | 2024-02-07 18:08:03,052 - INFO in packer @ start: Destination temp/packed_series directory created successfully<br>
petfectior-client  | 2024-02-07 18:08:03,053 - INFO in packer @ start: SeriesPacker started<br>
petfectior-client  | 2024-02-07 18:08:03,056 - INFO in uploader @ start: Uploader started<br>
petfectior-client  | 2024-02-07 18:08:03,059 - INFO in downloader @ start: Started<br>
petfectior-client  | 2024-02-07 18:08:03,060 - INFO in unpacker @ start: Destination temp/unpacked_series directory created successfully<br>
petfectior-client  | 2024-02-07 18:08:03,061 - INFO in unpacker @ start: Unpacker started<br>
petfectior-client  | 2024-02-07 18:08:03,061 - INFO in store_scu @ start: StoreSCU started<br>
petfectior-client  | 2024-02-07 18:08:03,062 - INFO in task_manager @ start: Task manager started<br>
6. Verificar que la interfaz web haya iniciado correctamente ingresando, desde un navegador web en cualquier dispositivo de la red local, al sitio:<br>
*http://server_ip:8000/config*
donde *server_ip* es la dirección del dispositivo donde se instaló la aplicación
7. En la pestaña "Processes" verificar que todos los procesos estén corriendo en estado 'Running' (excepto Server Monitor, que por defecto no inicia)
8. Iniciar el Server Monitor y verificar, en el indicador de conexión con el servidor, que el estado sea 'Alive'. Se recomienda monitorear este estado durante unos minutos
y luego detener el proceso para no sobrecargar al cliente y al servidor.

## Configuración inicial
### General
1. Ingresar a la interfaz de configuración de la aplicación: *http://server_ip:8000/config*
2. En el cuadro 'General configuration' editar la configuración para ingresar el Client ID provisto por el proveedor.
3. En el cuadro 'Local DICOM Application', editar la configuración para ingresar la dirección IP del dispositivo donde se instaló la aplicación como "IP Address". Esto no modifica la configuración de red del dispositivo ni de la aplicación; sólo sirve para tener fácilmente accesible el dato de la dirección IP de la aplicación.

### Configuración de dispositivos remotos
Cualquier dispositivo al que la aplicación deba enviar imágenes procesadas debe ser configurado. Para esto:
1. Ir a *http://server_ip:8000/config*
2. En el cuadro 'Remote DICOM devices', click en 'New'. Completar con los datos de la aplicación DICOM remota:
    - Name: puede ser cualquier cosa (p.ej. PET, Workstation, PACS) ya que solo sirve para identificar el dispositivo internamente
    - AE Title: el AE Title de la aplicación DICOM donde el dispositivo remoto recibe imágenes.
    - IP Address: la dirección IP del dispositivo remoto (en la red local)
    - Port: puerto TCP donde escucha la aplicación DICOM donde el dispositivo remoto recibe imágenes.
    - Use as destination: si está tildado, todas las imágenes procesadas, se enviarán a este dispositivo, sin importar si se originaron en otro dispositivo.
Con el botón 'Edit' se puede modificar esta configuración más tarde.

### Manejo de destinos
El flujo de trabajo de la aplicación es el siguiente: recibe DICOMS, envía las imágenes para ser procesadas, recibe las imágenes procesadas, construye los DICOMS, y los envía. En algún punto, se debe decidir cuáles serán los destinos a los cuáles se enviarán las imágenes procesadas. Hay dos posibles configuraciones para esto:
- Destinos fijos: aquellos en los que se haya seleccionado la opción "use as destination".
- "Mirror mode": esto se activa en el cuadro 'General configuration' de la pestaña *config*. Si está activado, la aplicación enviará las imágenes procesadas a aquel dispositivo con la dirección IP desde la cual recibió las imágenes a procesar. Si hay más de un dispositivo que matchee la IP, las enviará a aquella aplicación con el AE title desde el cual recibió las imágenes a procesar; si ninguno coincide, enviará a las imágenes a todos los dispositivos que matcheen la IP. Esto no anula los destinos seteados como fijos.

# Instrucciones de uso básico

### ¿Cómo procesar un estudio PET?
1. Configurar PETfectior como un nodo DICOM en el dispositivo desde el que se quiera enviar las imágenes para procesar, usando los valores de dirección IP, puerto y AE title mostrados en la pestaña config.
2. Enviar la serie PET a procesar a este destino DICOM.
3. Para que el procesamiento comience, debe existir al menos un nodo de destino para las imágenes procesadas. Ver la sección "Configuración de dispositivos remotos" y "Manejo de destinos" para más información.
4. La serie procesada llegará por DICOM al dispositivo de destino una vez completado el procesamiento. No requiere ninguna otra interacción del operador.

### ¿Cómo monitorear el estado de procesamiento de un estudio?
Cada vez que una serie DICOM se envía para ser procesada, se genera una nueva tarea en la aplicación. 
En la pestaña 'Tasks' de la interfaz web de la aplicación (*http://server_ip:8000/tasks*) se puede ver una lista con información de las tareas y su estado.
Si un tarea muestra un mensaje de falla, se pueden rastrear los mensajes generados por la aplicación en la pestaña 'Logs'. Usar el campo 'Last update' de la tarea fallida para filtrar los mensajes cercanos a la falla.








