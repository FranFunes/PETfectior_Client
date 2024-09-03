Flujo de trabajo de procesamiento
=================================

| El procesamiento de los estudios se divide en varias etapas, llevadas a cabo por diferentes **servicios**
  (implementados como python threads), que corren en paralelo, y se organiza en objetos **Task**, cada
  uno de los cuales representa una tarea. La tarea es la unidad mínima de información que se enviará a
  procesar, y se corresponde con una serie DICOM PET. Los servicios intercambian entre sí información de
  las tareas a procesar a través de colas python (Queues).
| A continuación se describe cada una de estas etapas de procesamiento y el servicio correspondiente.

Envío de imágenes a procesar
----------------------------

Recepción de imágenes DICOM
~~~~~~~~~~~~~~~~~~~~~~~~~~~
La aplicación implementa un servicio :ref:`dicom-storage-service-class-provider`, que escucha en un puerto TCP
esperando que otra aplicación DICOM en la red del cliente le envíe imágenes PET (las imágenes de otras modalidades
son ignoradas). Cuando recibe una imagen (instancia) PET:

 1. Verifica que existan ciertos campos mandatorios en el encabezado DICOM, y extrae los necesarios para
    continuar el procesamiento.
 2. Guarda en base de datos información DICOM a nivel de instancia, serie, estudio y paciente
    (creando los elementos que no existan o actualizándolos si ya existen)
 3. Guarda el archivo DICOM en disco.
 4. Pone los datos DICOM extraídos, junto con los datos del dispositivo de origen, en la cola de salida.

Compilator
~~~~~~~~~~~
Este servicio se encarga de agrupar (compilar) las instancias individuales pasadas por el Store SCP en series
DICOM completas, y asociarle a cada serie una tarea. Instancias repetidas se asignan a tareas distintas.
Luego de 5 segundos de inactividad, el proceso revisa si alguna de las tareas está lista para ser enviada
al paso siguiente. Para eso, debe cumplir algunos criterios:

 * Debe tener una cantidad mínima de imágenes (configurable en base de datos).
 * Deben haberse recibido la cantidad esperada de imágenes (leída del campo DICOM NumberOfSlices) si es 
   conocida, o bien las imágenes recibidas deben ser contiguas (sin huecos mayores a cierta dimensión
   configurable en base de datos).

Las tareas listas se ponen en la cola de salida. Las que estén incompletas e inactivas por más de cierto
tiempo (configurable en base de datos), se abortan.

Validator
~~~~~~~~~
Este servicio verifica que la tarea pueda ser procesada por el servidor remoto. Para eso, debe cumplir los
siguientes criterios:

 * Debe haberse fijado el destino final (DICOM) de las imágenes procesadas.
 * La información del encabezado DICOM debe estar completa.
 * El radiofármaco debe ser conocido.
 * El servidor remoto debe validar la licencia de uso para ese radiofármaco y la existencia de un algoritmo
   de procesamiento adecuado. Esto se hace a través de una API HTTP expuesta por el servidor a tal fin.

Las tareas validadas se ponen en la cola de salida. Las que no cumplen alguno de los criterios se abortan.

Packer
~~~~~~
Este servicio extrae los valores de voxel de la imagen a procesar en un numpy array, los guarda en 
un archivo {task_id}.npy junto con un archivo metadata.json con los metadatos necesarios para el procesamiento
y genera un archivo comprimido para enviar al servidor.

Uploader
~~~~~~~~~
Este servicio copia el archivo comprimido a una carpeta compartida con el servidor remoto a través de una
VPN establecida a tal fin. Luego, envía un mensaje a la API del servidor, para iniciar el procesamiento.

Descarga de imágenes procesadas
-------------------------------
Cuando el servidor finaliza un procesamiento, escribe un archivo lo indica a PETfectior Client a través de un request a la 
:doc:`api`, que dispara la descarga de los datos procesados de esa tarea.

Downloader
~~~~~~~~~~
Este servicio copia el archivo {task_id}.zip escrito por el servidor con los resultados, desde la carpeta
compartida al almacenamiento local.

Unpacker
~~~~~~~~
Este servicio descomprime el archivo {task_id}.zip con los datos de pixel procesados, aplica diferentes
filtros de suavizado configurados por el cliente, y genera una o más series de objetos DICOM correspondientes
al paciente y estudio originalmente vinculados a la tarea.
Los filtros de suavizado son de tipo gaussiano, isotrópicos, puede ser configurados por el cliente a través
de la interfaz de usuario, y su configuración se almacena en base de datos.
Una vez reconstruidos los objetos DICOM, se colocan en la cola de salida para ser enviados.

Envío de imágenes DICOM
~~~~~~~~~~~~~~~~~~~~~~~~
Este servicio envía los objetos DICOM generados en el paso anterior a los destinados configurados para cada
tarea.

