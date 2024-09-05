$(document).ready(function () {
    // Initialize AppConfig
    $.ajax({
        url: "/get_app_config",   
        contentType: "application/json",
        success: function(response) {                    
            // Update data
            $("#clientID").text(response.client_id)  
            $( "#mirrorMode" ).prop( "checked", response.mirror_mode )  
            $('#localConfigAdminUser').val(response.username)
            $('#localConfigAdminPass').val(response.password)
        },
        error: function(xhr, status, error) {
            // handle error response here
            $("#clientID").text('No disponible - error del servidor')
            $( "#mirrorMode" ).prop( "checked", false )              
        }
        }); 

    // Initialize local device
    $.ajax({
        url: "/get_local_device",   
        contentType: "application/json",
        success: function(response) {                    
            // Update local device info
            $("#localAET").text(response.data.ae_title)
            $("#localIP").text(response.data.address)
            $("#localPort").text(response.data.port)   
        },
        error: function(xhr, status, error) {
            // handle error response here
            console.log(xhr.responseText);
        }
    }); 

    // Initialize PET models names in filter settings modal
    $.ajax({
        url: "/get_pet_models",   
        contentType: "application/json",
        success: function(response) {                    
            // Update local device info         
            for (let model of response) {
                var option = $(`<option value="${model}">${model}</option>`)
                $("#postfilterModelName").append(option)        
            }
        },
        error: function(xhr, status, error) {
            // handle error response here
            console.log(xhr.responseText);
        }
    });    

    // Initialize devices table
    var devices_table = $('#devices').DataTable({
        ajax: "/get_remote_devices",
        columns: [            
            { data: 'name', title:'Nombre' },
            { data: 'ae_title', title: 'AE Title' },
            { data: 'address', title: 'Dirección IP' },
            { data: 'is_destination', title: 'Usar como destino', render: (data) => data ? 'Sí' : 'No' }
        ],
        searching: false,
        paging: false,
        ordering: false,
        info: false,
        language: {
            "emptyTable": "No hay dispositivos remotos configurados"
          } 
    });

    // Initialize filterSettings table
    var postFilter_table = $('#postfilterSettings').DataTable({
        ajax: "/recon_settings",
        columns: [            
            { data: 'id', visible: false },
            { data: 'description', title:'Nombre de la serie' },
            { data: 'mode', title:'Asignacion de nombre', render: (data) => data == 'replace' ? 'reemplazar' : 'agregar'},
            { data: 'model', title:'Modelo PET', render: (data) => data == 'all' ? 'Todos' : data },
            { data: 'radiopharmaceutical', title:'Radiofármaco', render: (data) => data == 'all' ? 'Todos' : data },
            { data: 'series_number', title:'Número de serie', name: "series_number"},
            { data: 'fwhm', title: 'FWHM' },
            { data: 'noise', title: 'Ruido %' },
            { data: 'enabled', title: 'Activada', render: (data) => data ? 'Sí' : 'No'},            
        ],
        searching: false,
        paging: false,
        ordering: false,
        info: false,
        language: {
            "emptyTable": `No hay filtros configurados. Las imágenes procesadas se enviarán
            como estan, sin ningún post-filtro. Use el botón "Nuevo" para configurar uno o más
            post-filtros gaussianos 3D isotrópicos`
          }
    });

    // Initialize radiopharmaceuticals table
    var rf_table = $('#radiopharmaceuticals').DataTable({
        ajax: "/radiopharmaceuticals",
        columns: [                        
            { data: 'name', title:'Nombre', name: "name"},
            { data: 'half_life', title:'Vida media'},
            { data: 'synonyms', title:'DICOM header'},        
        ],
        searching: false,
        paging: false,
        ordering: false,
        info: false,
        language: {
            "emptyTable": "No hay radiofármacos configurados."
          },
        initComplete: function () {
            // Initialize radiopharmaceuticals names in filter settings modal
            for (let rf of rf_table.column("name:name").data().toArray()) {
                var option = $(`<option value="${rf}">${rf}</option>`)
                $("#postfilterRFName").append(option)        
            }
        }
    });

    // Enable select behaviour for tables
    $('table tbody').on('click', 'tr', function () {   
        var thisTable = $(this).closest('table').DataTable();
        if (!$(this).hasClass('selected')) { 
            thisTable.rows().deselect()
            thisTable.row($(this)).select()
        }
        else {
            thisTable.rows().deselect()
        }
    });

    // App config manager
    $("#editLocalConfig").on('click', function () {    
        // Fill form with local device info        
        $('.modal-title').text('Editar configuración de la aplicación') 
        $('#localConfigClientID').val($("#clientID").text()) 
        $( "#localConfigMirrorMode" ).prop( "checked", $( "#mirrorMode" ).prop( "checked" )) 

    })
    $("#localAppConfigForm").submit(function(event) {
        // Prevent the form from submitting normally
        event.preventDefault();      
        var ajax_data = {
            "client_id":  $('#localConfigClientID').val(),
            "mirror_mode": $("#localConfigMirrorMode").prop("checked"),
            "username": $('#localConfigAdminUser').val(),
            "password": $('#localConfigAdminPass').val()
        }
        $.ajax({
            url: "/manage_app_config",
            method: "POST",
            data:   JSON.stringify(ajax_data),
            dataType: "json",
            contentType: "application/json",
            success: function(response) {                    
                // Show success message
                alert(response.message)
                // Update local device info                 
                $('#clientID').text(ajax_data.client_id)
                $("#mirrorMode").prop("checked", ajax_data.mirror_mode)
            },
            error: function(xhr, status, error) {
                // handle error response here
                alert("Error al actualizar la configuración");
            }
            });  
    });  
    
    // Local device manager
    $("#editLocalDevice").on('click', function () {    
        // Fill form with local device info
        $('#localDeviceManagerIP').val($("#localIP").text())  
        $('#localDeviceManagerAET').val($("#localAET").text())  
        $('.modal-title').text('Editar la configuración DICOM local')      
    })

    // Edit local device form submit
    $("#localDeviceManagerForm").submit(function(event) {
        // Prevent the form from submitting normally
        event.preventDefault();      
        var ajax_data = {
            "ae_title":  $('#localDeviceManagerAET').val(),
            "address":  $('#localDeviceManagerIP').val()
        }
        $.ajax({
            url: "/manage_local_device",
            method: "POST",
            data:   JSON.stringify(ajax_data),
            dataType: "json",
            contentType: "application/json",
            success: function(response) {                    
                // Show success message
                alert(response.message)
                // Update local device info
                $("#localAET").text(ajax_data.ae_title)
                $("#localIP").text(ajax_data.address)
            },
            error: function(xhr, status, error) {
                // handle error response here
                alert(xhr.responseJSON.message);
            }
            });  
    });    

    // Remote device manager
    var deviceAction

    // Adapt modal contents depending on selected action
    $("#newDevice").on('click', function () {
        deviceAction = "add"
        // Reset form
        $("#deviceManagerForm")[0].reset()
        $('.modal-title').text('Añadir un dispositivo')
        $('#deviceManagerName').prop('disabled', false)       
    })
    
    $("#editDevice").on('click', function () {                
        // If there are any selected rows, show modal
        var selectedRows = devices_table.rows({ selected: true })
        
        if (selectedRows.count() > 0) {         
            $('#deviceModal').modal('show');   
            // Fill form with selected device info
            $('.modal-title').text('Editar un dispositivo')
            $('#deviceManagerName').prop('disabled',true)

            data = selectedRows.data()[0]            
            $('#deviceManagerName').val(data.name)
            $('#deviceManagerAET').val(data.ae_title)
            $('#deviceManagerIP').val(data.address.split(":")[0])
            $('#deviceManagerPort').val(data.address.split(":")[1])
            $( "#deviceManagerIsDest" ).prop( "checked", data.is_destination ) 

            deviceAction = "edit"        
        }                
    })    

    // Delete device
    $("#deleteDevice").on('click', function () {

        var ajax_data = devices_table.rows({ selected: true }).data()[0]
        ajax_data.action = "delete"
        if (confirm(`Eliminar dispositivo ${ajax_data.name}?`)){
            $.ajax({
                url: "/manage_remote_devices",
                method: "POST",
                data:   JSON.stringify(ajax_data),
                dataType: "json",
                contentType: "application/json",
                success: function(response) {                    
                    // Show success message
                    alert(response.message)
                    devices_table.ajax.reload()
                },
                error: function(xhr, status, error) {
                    // handle error response here
                    alert(xhr.responseJSON.message);
                }
            }); 
        }
    })

    // New/Edit form submit
    $("#deviceManagerForm").submit(function(event) {
        // Prevent the form from submitting normally
        event.preventDefault();      
        var ajax_data = {
            "action": deviceAction,
            "name": $('#deviceManagerName').val(),
            "ae_title":  $('#deviceManagerAET').val(),
            "address": $('#deviceManagerIP').val(),
            "port": $('#deviceManagerPort').val(),
            "is_destination": $("#deviceManagerIsDest").prop("checked")
        }
        $.ajax({
            url: "/manage_remote_devices",
            method: "POST",
            data:   JSON.stringify(ajax_data),
            dataType: "json",
            contentType: "application/json",
            success: function(response) {                    
                // Show success message
                alert(response.message)
                devices_table.ajax.reload()
            },
            error: function(xhr, status, error) {
                // handle error response here
                alert(xhr.responseJSON.message);
            }
            });     
    });

    // Ping remote device
    $("#pingRemoteDevice").on('click', function(event) {
        // Prevent the form from submitting normally
        event.preventDefault();     

        $(this)[0].innerHTML = `<span class="spinner-border spinner-border-sm"></span>`
        $(this).prop('disabled', true);
                
        var ajax_data = {
            "address": $('#deviceManagerIP').val()
        }
        $.ajax({
            url: "/ping_remote_device",
            method: "POST",
            data:   JSON.stringify(ajax_data),
            dataType: "json",
            contentType: "application/json",
            success: function(response) {                    
                // Show success message
                $("#pingRemoteDevice")[0].innerHTML = 'Correcto'
                $("#pingRemoteDevice").prop('disabled', false)
                $("#pingRemoteDevice").addClass('btn-success')
                $("#pingRemoteDevice").removeClass('btn-danger')

            },
            error: function(xhr, status, error) {
                // handle error response here
                $("#pingRemoteDevice")[0].innerHTML = 'Fallo'
                $("#pingRemoteDevice").prop('disabled', false)
                $("#pingRemoteDevice").addClass('btn-danger')
                $("#pingRemoteDevice").removeClass('btn-success')

            }
        });
    });

    // Echo remote device
    $("#echoRemoteDevice").on('click', function(event) {
        // Prevent the form from submitting normally
        event.preventDefault();     

        $(this)[0].innerHTML = `<span class="spinner-border spinner-border-sm"></span>`
        $(this).prop('disabled', true);
        
        var ajax_data = {
            "ae_title":  $('#deviceManagerAET').val(),
            "address": $('#deviceManagerIP').val(),
            "port": parseInt($('#deviceManagerPort').val()),
        }
        
        $.ajax({
            url: "/echo_remote_device",
            method: "POST",
            data:   JSON.stringify(ajax_data),
            dataType: "json",
            contentType: "application/json",
            success: function(response) {                    
                // Show success message
                $("#echoRemoteDevice")[0].innerHTML = 'Correcto'
                $("#echoRemoteDevice").prop('disabled', false)
                $("#echoRemoteDevice").addClass('btn-success')
                $("#echoRemoteDevice").removeClass('btn-danger')
            },
            error: function(xhr, status, error) {
                // handle error response here
                $("#echoRemoteDevice")[0].innerHTML = 'Fallo'
                $("#echoRemoteDevice").prop('disabled', false)
                $("#echoRemoteDevice").addClass('btn-danger')
                $("#echoRemoteDevice").removeClass('btn-suc cess')
            }
        });
    });

    // Reset ping/echo buttons when modal is closed
    $('#deviceModal').on('hidden.bs.modal', function () {        
        $('#pingRemoteDevice').removeClass('btn-danger').removeClass('btn-success').addClass('btn-primary').text('Ping')
        $('#echoRemoteDevice').removeClass('btn-danger').removeClass('btn-success').addClass('btn-primary').text('Echo')
    });

    // Radiofarmaceutical management
    var rfAction

    // Adapt modal contents depending on selected action
    $("#newRadiopharmaceutical").on('click', function () {
        rfAction = "add"        
        // Reset form
        $('#radiopharmaceuticalName').prop('disabled', false)
        $("#radiopharmaceuticalForm")[0].reset()
        $('.modal-title').text('Añadir radiofármaco')              
    })
    
    $("#editRadiopharmaceutical").on('click', function () {                
        // If there are any selected rows, show modal
        var selectedRows = rf_table.rows({ selected: true })
        
        if (selectedRows.count() > 0) {         
            $('#radiopharmaceuticalModal').modal('show');   
            // Fill form with selected device info
            $('.modal-title').text('Editar radiofármaco')            

            data = selectedRows.data()[0]            
            $('#radiopharmaceuticalName').val(data.name)
            $('#radiopharmaceuticalName').prop('disabled', true)
            $('#radiopharmaceuticalSynonyms').val(data.synonyms)
            $('#radiopharmaceuticalHalflife').val(data.half_life)
            
            rfAction = "edit"        
        }                
    })    

    // Delete radiopharmaceutical
    $("#deleteRadiopharmaceutical").on('click', function () {

        var ajax_data = rf_table.rows({ selected: true }).data()[0]
        ajax_data.action = "delete"
        if (confirm(`Eliminar radiofármaco "${ajax_data.name}"?`)){
            $.ajax({
                url: "/radiopharmaceuticals",
                method: "POST",
                data:   JSON.stringify(ajax_data),
                dataType: "json",
                contentType: "application/json",
                success: function(response) {                    
                    // Show success message
                    alert(response.message)
                    rf_table.ajax.reload()
                },
                error: function(xhr, status, error) {
                    // handle error response here
                    alert(xhr.responseJSON.message);
                }
            }); 
        }
    })

    // New/Edit form submit
    $("#radiopharmaceuticalForm").submit(function(event) {
        // Prevent the form from submitting normally
        event.preventDefault();      
        var ajax_data = {
            "action": rfAction,
            "name": $('#radiopharmaceuticalName').val(),
            "half_life": $('#radiopharmaceuticalHalflife').val(),
            "synonyms": $('#radiopharmaceuticalSynonyms').val()
        }   
        $.ajax({
            url: "/radiopharmaceuticals",
            method: "POST",
            data:   JSON.stringify(ajax_data),
            dataType: "json",
            contentType: "application/json",
            success: function(response) {                    
                // Show success message
                alert(response.message)
                rf_table.ajax.reload()
            },
            error: function(xhr, status, error) {
                // handle error response here
                alert(xhr.responseJSON.message);
            }
            });     
    });
    
    // Post filter settings manager
    var postfilterAction

    // Adapt modal contents depending on selected action
    $("#newPostfilter").on('click', function () {
        postfilterAction = "add"
        var sn = Math.max(...postFilter_table.column('series_number:name').data().toArray()) + 1 ?? 1001
        // Reset form
        $("#postfilterManagerForm")[0].reset()
        $('.modal-title').text('Añadir post-filtro')           
        $('#postfilterSeriesNumber').val(sn)        
    })
    
    $("#editPostfilter").on('click', function () {                
        // If there are any selected rows, show modal
        var selectedRows = postFilter_table.rows({ selected: true })
        
        if (selectedRows.count() > 0) {         
            $('#postfilterModal').modal('show');   
            // Fill form with selected device info
            $('.modal-title').text('Editar post-filtro')            

            data = selectedRows.data()[0]            
            $('#postfilterDescription').val(data.description)
            $('#postfilterModelName').val(data.model)
            $('#postfilterRFName').val(data.radiopharmaceutical)
            $('#postfilterSeriesNumber').val(data.series_number)
            $('#postfilterFWHM').val(data.fwhm)
            $( "#postfilterEnabled" ).prop( "checked", data.enabled) 
            $("#postfilterMode").val(data.mode)
            $("#postfilterNoise").val(data.noise)
            

            postfilterAction = "edit"        
        }                
    })    

    // Delete postfilter settings
    $("#deletePostfilter").on('click', function () {

        var ajax_data = postFilter_table.rows({ selected: true }).data()[0]
        ajax_data.action = "delete"
        if (confirm(`Eliminar recon "${ajax_data.description}"?`)){
            $.ajax({
                url: "/recon_settings",
                method: "POST",
                data:   JSON.stringify(ajax_data),
                dataType: "json",
                contentType: "application/json",
                success: function(response) {                    
                    // Show success message
                    alert(response.message)
                    postFilter_table.ajax.reload()
                },
                error: function(xhr, status, error) {
                    // handle error response here
                    alert(xhr.responseJSON.message);
                }
            }); 
        }
    })

    // New/Edit form submit
    $("#postfilterManagerForm").submit(function(event) {
        // Prevent the form from submitting normally
        event.preventDefault();      
        var ajax_data = {
            "action": postfilterAction,
            "id": postfilterAction == "add" ? "" : postFilter_table.rows({ selected: true }).data()[0].id,
            "description": $('#postfilterDescription').val(),
            "model": $('#postfilterModelName').val(),
            "radiopharmaceutical": $('#postfilterRFName').val(),
            "series_number": $('#postfilterSeriesNumber').val()|1000,
            "mode": $("#postfilterMode").val(),
            "fwhm":  $('#postfilterFWHM').val(),
            "noise":  $('#postfilterNoise').val(),
            "enabled": $('#postfilterEnabled').prop("checked")
        }
        $.ajax({
            url: "/recon_settings",
            method: "POST",
            data:   JSON.stringify(ajax_data),
            dataType: "json",
            contentType: "application/json",
            success: function(response) {                    
                // Show success message
                alert(response.message)
                postFilter_table.ajax.reload()
            },
            error: function(xhr, status, error) {
                // handle error response here
                alert(xhr.responseJSON.message);
            }
            });     
    });  

});

// Don't show alerts on ajax errors
$.fn.dataTable.ext.errMode = 'throw';