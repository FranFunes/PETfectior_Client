$(document).ready(function () {

    var tasks_table = $('#tasks').DataTable({
        ajax: "/get_tasks_table", 
        columns: [            
            { data: 'source', title: 'Source' },
            { data: 'destinations', title: 'Destinations' },
            { data: 'PatientName', title: 'Patient' }, 
            { data: 'StudyDate', title: 'Date', type: 'date' }, 
            { data: 'description', title: 'Series' },
            { data: 'imgs', title: 'Imgs' },
            { data: 'started', title: 'Started' },
            { data: 'status', title: 'State' },
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
        searching:      false,
        info:           false,
        select:         {
                            style: 'os',
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
        selectedRows = tasks_table.rows({ selected: true })
        task_ids = selectedRows.data().toArray().map(item => item.task_id)
        $.ajax({
            url: "/task_action",
            method: "POST",
            data: JSON.stringify({
                'action': $(this).attr('id'),                
                'ids': task_ids,
            }),
            contentType:'application/json'
        })
    })
});

// Don't show alerts on ajax errors
//$.fn.dataTable.ext.errMode = 'throw';