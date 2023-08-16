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

    // Enable select behaviour for device table
    $('#devices tbody').on('click', 'tr', function () {                
        if (!$(this).hasClass('selected')) {                  
            devices_table.rows().deselect()
            devices_table.row($(this)).select()
        }
        else {
            devices_table.rows().deselect()
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
        $('#localDeviceManagerAET').val($("#localAET").text())  
        $('.modal-title').text('Edit local DICOM configuration')      
    })

    // Edit local device form submit
    $("#localDeviceManagerForm").submit(function(event) {
        // Prevent the form from submitting normally
        event.preventDefault();      
        var ajax_data = {
            "ae_title":  $('#localDeviceManagerAET').val()
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

    

});





// Don't show alerts on ajax errors
$.fn.dataTable.ext.errMode = 'throw';