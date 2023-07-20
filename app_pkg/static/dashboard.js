$(document).ready(function () {

    var table_processes = $('#processes').DataTable({
        ajax: "/get_services_status",            
        columns: [
            { data: 'service_name', title: 'Service' },
            { data: 'status', title: 'Status' },
            {   
                title: 'Start',
                defaultContent: '<button class="btn btn-primary">Start</button>',
                class: 'startServiceBtn'
            },
            {
                title: 'Stop',
                defaultContent: '<button class="btn btn-danger">Stop</button>',
                class: 'stopServiceBtn'
            },
            /*
            {
                title: 'Logs',
                defaultContent: `<a href="#" class="link-primary"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-search" viewBox="0 0 16 16">
                <path d="M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001c.03.04.062.078.098.115l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85a1.007 1.007 0 0 0-.115-.1zM12 6.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0z"/>
              </svg></a>`,
                class: 'showLogsBtn'

            }*/
        ],
        processing:     false,
        paging:         false,
        scrollX:        true,  
        searching:      false,  
        info:           false,
        ordering:       false,
    });
    
    // Add event listener for starting services
    $('#processes tbody').on('click', 'td.startServiceBtn', function () {
        
        var tr = $(this).closest('tr');
        var row = table_processes.row(tr);
        ajax_data = row.data()
        ajax_data.action = 'start'
        $.ajax({
            url: "/manage_service",
            method: "POST",
            data:   JSON.stringify(ajax_data),
            dataType: "json",
            contentType: "application/json",
            success: function(response) {                    
                // Show success message
                alert(response.result)
            },
            error: function(xhr, status, error) {
                // handle error response here
                alert(xhr.responseJSON.message);
            }
            });  
    });  

    // Add event listener for stopping services
    $('#processes tbody').on('click', 'td.stopServiceBtn', function () {
        
        var tr = $(this).closest('tr');
        var row = table_processes.row(tr);
        ajax_data = row.data()
        ajax_data.action = 'stop'
        $.ajax({
            url: "/manage_service",
            method: "POST",
            data:   JSON.stringify(ajax_data),
            dataType: "json",
            contentType: "application/json",
            success: function(response) {                    
                // Show success message
                alert(response.result)
            },
            error: function(xhr, status, error) {
                // handle error response here
                alert(xhr.responseJSON.message);
            }
            });  
    });  

    
    var table_monitor = $('#monitor').DataTable({
        ajax: "/check_server_connection",            
        columns: [
            { data: 'state', title: 'Server connection state' },
            { data: 'state_duration', title: 'State duration' },
            { data: 'total_disconnections', title: 'Disconnections' },
            { data: 'total_uptime', title: 'Total uptime' },
            { data: 'total_downtime', title: 'Total downtime' },            
        ],
        processing:     false,
        paging:         false,
        scrollX:        true,  
        searching:      false,  
        info:           false,
        ordering:       false,
    });

    // Auto refresh
    setInterval( function () {
        table_processes.ajax.reload(); 

    }, 5000);
    setInterval( function () {
        table_monitor.ajax.reload();
    }, 1000);

});


// Don't show alerts on ajax errors
$.fn.dataTable.ext.errMode = 'throw';