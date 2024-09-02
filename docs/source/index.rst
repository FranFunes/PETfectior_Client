.. PETfectior documentation master file, created by
   sphinx-quickstart on Fri Aug 30 10:54:59 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

PETfectior Client
========================

¿Qué es PETfectior?
-------------------
PETfectior es una aplicación para eliminación de ruido en imágenes de Tomografía por Emisión de Positrones 
(PET). Actualmente, se encuentra en proceso de registro ante ANMAT para poder ser distribuído 
como un producto médico.

¿Qué es PETfectior Client?
--------------------------
PETfectior funciona con una lógica cliente-servidor: las imágenes a procesar deben ser enviadas, a través
de internet, desde el equipo, workstation o red informática del usuario final (cliente) a un servidor
de procesamiento centralizado.
PETfectior Client funciona como intermediario entre la red del cliente y el servidor de procesamiento, y
cumple las siguientes funciones:

 * Simplifica el flujo de trabajo exponiendo una interfaz DICOM hacia la red del cliente. 
   El usuario final solo tiene que enviar por DICOM las imágenes a procesar a esta interfaz,
   y recibirá las imágenes procesadas, también por DICOM.
 * Valida las imágenes recibidas, asegurándose que el servidor remoto sea capaz de procesarlas.
 * Extrae del DICOM recibido los valores de píxel y los metadatos necesarios para el procesamiento,
   eliminando todos los datos identificatorios del paciente.
 * Envía los datos extraídos al servidor remoto para su procesamiento.
 * Recibe los datos procesados, genera los objetos DICOM, y los envía a los nodos de destino.
 * Proporciona una interfaz gráfica de usuario, accesible desde cualquier navegador web de la red, para
   el seguimiento de las tareas enviadas, el monitoreo y configuración de la herramienta, y el rastreo
   y solución de errores.

Guía de usuario
---------------
El :doc:`user/index` es el documento de referencia que el usuario final debe consultar para saber cómo 
instalar, configurar y usar la herramienta.

Referencia
----------
La :doc:`reference/index` contiene una descripción de la lógica y el funciomiento interno de los diferentes módulos
de código que componen la aplicación, apuntando principalmente a facilitar el proceso de auditorías de
código por parte de terceros.

.. toctree::
   :maxdepth: 2
   :caption: Contenidos:
   :hidden:
   
   user/index
   reference/index