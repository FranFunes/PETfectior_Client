import pandas as pd
from datetime import datetime

class TaskManager():

    def __init__(self):

        # Read previous session data, or initialize data
        try:
            data = pd.read_csv('config/tasks.csv')
        except:    
            columns = ['task_id',
                       'source',
                       'PatientName',
                       'StudyDate',
                       'description',
                       'started',
                       'status',
                       'updated',
                       'imgs',
                       'destinations'
                       ]  
            data = pd.DataFrame(columns = columns).set_index('task_id')                  

        self.data = data

    def _new_task(self, task_data):

        # Append new task to the database          
        task_id = task_data['task_id']      
        columns = self.data.columns
        row = {col: task_data.get(col, '') for col in columns}        
        row = pd.DataFrame(row, index = [task_id])
        self.data = pd.concat([self.data, row])
    
    def manage_task(self, action, task_id = None, task_data = None):

        if action == 'new':
            self._new_task(task_data)
        elif action == 'update':            
            for key, value in task_data.items():
                self.data.loc[task_id, key] = value
            self.data.loc[task_id,'updated'] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        elif action == 'clear_failed':
            to_delete = self.data[(self.data['status'] == 'failed')].index
            self.data.drop(to_delete, inplace = True)
        elif action == 'clear_finished':
            to_delete = self.data[(self.data['status'] == 'finished')].index
            self.data.drop(to_delete, inplace = True)
    
    def get_tasks_table(self):

        data = []

        for task_id, task_data in self.data.iterrows():            
            row = task_data.to_dict()
            row['task_id'] = task_id
            data.append(row)

        return data        
    

                



        