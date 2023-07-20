$(document).ready(function () {
    
    //Init processes list
    $.ajax({
        url: "/get_modules_names",
        success: function(response) {                    
            // Show success message
            $.each(response.data, function(key, value) {                                
                $('#process-select')
                     .append($('<option>', { value : value })
                     .text(value));                
                // Show last value selected
                if (localStorage.getItem('process') !== null ) {                   
                    $('#process-select').val(localStorage.getItem("process"))                    
                }                
           });
        },
        error: function(xhr, status, error) {
            // handle error response here
            console.log(xhr.responseText);
        }
        });    

   // Init logs table
    var ignore_post = true
    var table_logs = $('#logs').DataTable({
        ajax: {
            url: "/get_logs",
            method: "POST",
            data: function() {
                    return JSON.stringify({
                        'dateSelector':$("[name='datetime']:checked").val(),
                        'startDate': $("#startDate").val(),
                        'endDate': $("#endDate").val(),
                        'startTime': $("#startTime").val(),
                        'endTime': $("#endTime").val(),    
                        'ignore': ignore_post, 
                        'process': $("#process-select").val(),
                        'levels': $("[name='level']:checked").map(function() {
                            return this.value
                        }).get(),
                    })
                },
            contentType: 'application/json',
            dataType: "json"
          },              
        columns: [
            { data: 'date', title: 'Date' },
            { data: 'time', title: 'Time' },
            { data: 'level', title: 'Level' },
            { data: 'module', title: 'Module' },
            { data: 'function', title: 'Function' },
            { data: 'message', title: 'Message' },
        ],
        processing:     false,
        paging:         true,
        scrollX:        true,  
        searching:      false,  
        info:           false,
        ordering:       false,
        dom: 'plt',        
        initComplete: function() {
            // Don't ignore post from now on
            ignore_post = false
            // Initialize table with data stored locally
            if (localStorage.getItem('logsTable') !== null) {
                data = JSON.parse(localStorage.getItem('logsTable'))
                table_logs.rows.add(data).draw()                
            }
        }
    });   
    
    // Show last query values in form
    // Processes
    if (localStorage.getItem('process') !== null ) {
        $('#process-select').val(localStorage.getItem("process"))
    }
    // Levels
    if (localStorage.getItem('levels') !== null ) {
        JSON.parse(localStorage.levels).forEach(function(item) {
            $("[name='level'][value='"+item+"']").prop('checked',true)
        })
    }

    if (localStorage.getItem('dateSelector') !== null ) {        
        // Dates and times
        $("#startDate").val(localStorage.getItem("startDate"))
        $("#endDate").val(localStorage.getItem("endDate"))
        $("#startTime").val(localStorage.getItem("startTime"))
        $("#endTime").val(localStorage.getItem("endTime"))
        $("#" + localStorage.getItem("dateSelector")).prop("checked", true)
        if (localStorage.getItem("dateSelector") == "date_range") {
            $('#startDate').prop("disabled", false)
            $('#endDate').prop("disabled", false)
            $('#startTime').prop("disabled", false)
            $('#endTime').prop("disabled", false)
        }        
        
    } else {
        $("#date_any").prop("checked", true)
        document.getElementById('startDate').valueAsDate = new Date()
        document.getElementById('endDate').valueAsDate = new Date()        
        document.getElementById('startTime').value = "00:00:00"
        document.getElementById('endTime').value = "23:59"
    }     
    
    // Enable/disable date pickers
    $("[name='datetime']").on('click', function(){

        console.log('date')
        if ($(this)[0].id == 'date_any') {
            $('#startDate').prop("disabled", true)
            $('#endDate').prop("disabled", true)
            $('#startTime').prop("disabled", true)
            $('#endTime').prop("disabled", true)
        }
        else {
            $('#startDate').prop("disabled", false)
            $('#endDate').prop("disabled", false)
            $('#startTime').prop("disabled", false)
            $('#endTime').prop("disabled", false)
        }
    })

    // Manage the logs search (form submission)
    $("#search_logs").submit(function(event) {
        // Prevent the form from submitting normally
        event.preventDefault();
        // Reload table
        table_logs.clear().draw()
        //Store the query data to be shown after refreshing the page        
        dateSelector = $("[name='datetime']:checked").prop('id')
        startDate = $("#startDate").val()
        endDate = $("#endDate").val()
        startTime = $("#startTime").val()
        endTime = $("#endTime").val()
        process = $("#process-select").val()
        levels = $("[name='level']:checked").map(function() {
            return this.value
        }).get()

        table_logs.ajax.reload(function() {
            // Store the data locally to be shown after refreshing the page    
            localStorage.setItem("logsTable",JSON.stringify(table_logs.rows().data().toArray()))
            localStorage.setItem("dateSelector", dateSelector)
            localStorage.setItem("startDate", startDate)
            localStorage.setItem("endDate", endDate)
            localStorage.setItem("startTime", startTime)
            localStorage.setItem("endTime", endTime)            
            localStorage.setItem("process", process)
            localStorage.setItem("levels", JSON.stringify(levels))
        })
    });   

    $("#export").on('click', function(event){
        event.preventDefault();

        // Create a .csv from table contents
        let data = table_logs.rows().data().toArray()
        let text = '';
        // Write headers
        headers = Object.keys(data[0])  
        text += headers.join(';')
        text += '\n'        
        // Write data
        for (item of data) {
            values = Object.values(item);
            text += values.join(';');
            text += '\n';
          }          

        // Create element with <a> tag
        const link = document.createElement("a");

        // Create a blog object with the file content which you want to add to the file
        const file = new Blob([text], { type: 'text/plain' });

        // Add file content in the object URL
        link.href = URL.createObjectURL(file);

        // Add file name
        link.download = "logs.csv";

        // Add click event to <a> tag to save file.
        link.click();
        URL.revokeObjectURL(link.href);
            })
});

// Don't show alerts on ajax errors
$.fn.dataTable.ext.errMode = 'throw';