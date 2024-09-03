.. _dicom-storage-service-class-provider:

DICOM Storage Service Class Provider
====================================

Este servicio se implementa mediante la siguiente clase, que a su vez se configura usando un handler adecuado
para el evento C-STORE:

.. autoclass:: app_pkg.services.store_scp.StoreSCP
   :members: __init__, echo


Para controlar cómo una Application Entity maneja los diferentes eventos DICOM que 
ocurren durante una asociación, `pynetdicom <https://pydicom.github.io/pynetdicom/stable/>`_ 
permite vincular un handler a cada tipo de evento (ver `Storage SCP <https://pydicom.github.io/pynetdicom/stable/examples/storage.html#storage-scp>`_ ).
En nuestro caso, se usa la función :ref:`db_store_handler <function-db-store-handler>`, cuya documentación se puede revisar para más detalles.