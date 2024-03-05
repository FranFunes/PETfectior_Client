$(document).ready(function () {
    // Initialize AppConfig
    $.ajax({
        url: "/get_app_config",   
        contentType: "application/json",
        success: function(response) {                    
            // Update data
            $("#clientID").text(response.client_id)  
            $("#serverURL").text(response.server_url)
            $( "#mirrorMode" ).prop( "checked", response.mirror_mode )  
            localStorage.setItem("sharedPath", response.shared_path)
        },
        error: function(xhr, status, error) {
            // handle error response here
            $("#clientID").text('Not available - server error')
            $("#serverURL").text('Not available - server error')
            $( "#mirrorMode" ).prop( "checked", false )  

            console.log(xhr.responseText);
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

    // Initialize devices table
    var devices_table = $('#devices').DataTable({
        ajax: "/get_remote_devices",
        columns: [            
            { data: 'name', title:'Name' },
            { data: 'ae_title', title: 'AE Title' },
            { data: 'address', title: 'IP Address' },
            { data: 'is_destination', title: 'Use as destination' }
        ],
        searching: false,
        paging: false,
        ordering: false,
        info: false,
        language: {
            "emptyTable": "No peer devices configured"
          } 
    });

    // Initialize filterSettings table
    var postFilter_table = $('#postfilterSettings').DataTable({
        ajax: "/recon_settings",
        columns: [            
            { data: 'id', visible: false },
            { data: 'suffix', title:'Suffix' },
            { data: 'fwhm', title: 'FWHM' },
            { data: 'enabled', title: 'Enabled' },            
        ],
        searching: false,
        paging: false,
        ordering: false,
        info: false,
        language: {
            "emptyTable": `No filter settings configured.
            Processed images will be sent as they are, without any post-filter.
            Use "New" button to configure one or more custom 3D isotropic gaussian filters.`
          }
    });

    // Enable select behaviour for tables
    $('#devices tbody').on('click', 'tr', function () {                
        if (!$(this).hasClass('selected')) {                  
            devices_table.rows().deselect()
            devices_table.row($(this)).select()
        }
        else {
            devices_table.rows().deselect()
        }
    });
    $('#postfilterSettings tbody').on('click', 'tr', function () {                
        if (!$(this).hasClass('selected')) {                  
            postFilter_table.rows().deselect()
            postFilter_table.row($(this)).select()
        }
        else {
            postFilter_table.rows().deselect()
        }
    });

    // App config manager
    $("#editLocalConfig").on('click', function () {    
        // Fill form with local device info        
        $('.modal-title').text('Edit App Configuration') 
        $('#localConfigClientID').val($("#clientID").text()) 
        $('#localConfigServerURL').val($("#serverURL").text()) 
        if (localStorage.getItem('sharedPath') !== null) {
            $('#localConfigSharedPath').val(localStorage.getItem('sharedPath'))            
        } else {
            $('#localConfigSharedPath').val("Unknown")
        }
        $( "#localConfigMirrorMode" ).prop( "checked", $( "#mirrorMode" ).prop( "checked" )) 

    })
    $("#localAppConfigForm").submit(function(event) {
        // Prevent the form from submitting normally
        event.preventDefault();      
        var ajax_data = {
            "client_id":  $('#localConfigClientID').val(),
            "server_url":  $('#localConfigServerURL').val(),
            "shared_path":  $('#localConfigSharedPath').val(),
            "mirror_mode": $("#localConfigMirrorMode").prop("checked")
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
                $('#serverURL').text(ajax_data.server_url)
                localStorage.setItem("sharedPath", ajax_data.shared_path)
                $("#mirrorMode").prop("checked", ajax_data.mirror_mode)
            },
            error: function(xhr, status, error) {
                // handle error response here
                alert("Update config failed");
            }
            });  
    });  
    
    // Local device manager
    $("#editLocalDevice").on('click', function () {    
        // Fill form with local device info
        $('#localDeviceManagerIP').val($("#localIP").text())  
        $('#localDeviceManagerAET').val($("#localAET").text())  
        $('.modal-title').text('Edit local DICOM configuration')      
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
        $('.modal-title').text('Add new device')
        $('#deviceManagerName').prop('disabled', false)       
    })
    
    $("#editDevice").on('click', function () {                
        // If there are any selected rows, show modal
        var selectedRows = devices_table.rows({ selected: true })
        
        if (selectedRows.count() > 0) {         
            $('#deviceModal').modal('show');   
            // Fill form with selected device info
            $('.modal-title').text('Edit device')
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
        console.log(ajax_data)
        if (confirm(`Delete device ${ajax_data.name}?`)){
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
                $("#pingRemoteDevice")[0].innerHTML = 'Success'
                $("#pingRemoteDevice").prop('disabled', false)
                $("#pingRemoteDevice").addClass('btn-success')
                $("#pingRemoteDevice").removeClass('btn-danger')

            },
            error: function(xhr, status, error) {
                // handle error response here
                $("#pingRemoteDevice")[0].innerHTML = 'Failed'
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
                $("#echoRemoteDevice")[0].innerHTML = 'Success'
                $("#echoRemoteDevice").prop('disabled', false)
                $("#echoRemoteDevice").addClass('btn-success')
                $("#echoRemoteDevice").removeClass('btn-danger')
            },
            error: function(xhr, status, error) {
                // handle error response here
                $("#echoRemoteDevice")[0].innerHTML = 'Failed'
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

    // Post filter settings manager
    var postfilterAction

    // Adapt modal contents depending on selected action
    $("#newPostfilter").on('click', function () {
        postfilterAction = "add"
        // Reset form
        $("#postfilterManagerForm")[0].reset()
        $('.modal-title').text('Add new postfilter')   
    })
    
    $("#editPostfilter").on('click', function () {                
        // If there are any selected rows, show modal
        var selectedRows = postFilter_table.rows({ selected: true })
        
        if (selectedRows.count() > 0) {         
            $('#postfilterModal').modal('show');   
            // Fill form with selected device info
            $('.modal-title').text('Edit postfilter settings')            

            data = selectedRows.data()[0]            
            $('#postfilterSuffix').val(data.suffix)
            $('#postfilterFWHM').val(data.fwhm)
            $( "#postfilterEnabled" ).prop( "checked", data.enabled ) 

            postfilterAction = "edit"        
        }                
    })    

    // Delete postfilter settings
    $("#deletePostfilter").on('click', function () {

        var ajax_data = postFilter_table.rows({ selected: true }).data()[0]
        ajax_data.action = "delete"
        if (confirm(`Delete recon "${ajax_data.suffix}"?`)){
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
            "suffix": $('#postfilterSuffix').val(),
            "fwhm":  $('#postfilterFWHM').val(),
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