$(document).ready(function () {

    var tasks_table = $('#tasks').DataTable({
        ajax: "/get_tasks_table", 
        columns: [            
            { data: 'PatientName', title: 'Patient' }, 
            { data: 'StudyDate', title: 'Date', type: 'date' }, 
            { data: 'status', title: 'State' },
            { data: 'source', title: 'Source' },
            { data: 'destinations', title: 'Destinations' },
            { data: 'description', title: 'Series' },
            { data: 'imgs', title: 'Imgs' },
            { data: 'started', title: 'Started' },
            { data: 'updated', title: 'Last update' },         
            { data: 'task_id', title: 'Task ID' }
        ],
        order: [[2, 'asc']],
        language: {
            search: 'Buscar',
            url: 'https://cdn.datatables.net/plug-ins/1.11.5/i18n/es-ES.json',
            emptyTable: "<br><br>",
            processing: " ",
        },
        processing:     false,
        paging:         false,
        scrollX:        true,  
        scrollY:        '500px',
        searching:      false,
        info:           false,
        select:         {
                            style: 'single',
                            selector: 'td',
                            info: false,
                        }
    });
    
    // Auto refresh, keeping selected rows and scrolling position
    setInterval( function () {
        var selectedRows = tasks_table.rows({ selected: true });
        var idx = selectedRows[0];

        var scrollingContainer = $(tasks_table.table().node()).parent('div.dataTables_scrollBody');
        var scrollTop = scrollingContainer.scrollTop();
               
        tasks_table.ajax.reload( function() {
            idx.forEach(function(element) {
                tasks_table.row(element).select();                
            })
            scrollingContainer.scrollTop(scrollTop);
        }); 
    }, 1000);

    // Add buttons functionality
    $('.task-action').on('click', function() {
        
        var ajax_data ={}
        action = $(this).attr('action')
        ajax_data["action"] = action
        
        if (['delete', 'restart', 'retry_last_step'].includes(action)) {
            ajax_data["task_id"] = tasks_table.row({ selected: true }).data().task_id
        }
        $.ajax({
            url: "/manage_tasks",
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
        }) 

});

// Don't show alerts on ajax errors
//$.fn.dataTable.ext.errMode = 'throw';