import logging, threading, os, traceback
from shutil import rmtree
from app_pkg import application, db
from app_pkg.db_models import Task, Patient, Study, Series, Instance

logger = logging.getLogger('__main__')

def delete_task(id):

    t = Task.query.get(id)
    if not t:
        return f"Task {id} doesn't exist", 500    
    if not t.step_state in [-1,2]:
        return "Sólo las tareas completadas o fallidas pueden ser eliminadas", 500    
    
    logger.info(f"trying to delete task {id}")
    db.session.delete(t)
    db.session.commit()
    return f"Tarea {id} eliminada exitosamente", 200

def restart_task(id):

    t = Task.query.get(id)
    if not t:
        return f"Task {id} doesn't exist", 500     
    if not t.step_state in [-1,2]:
        return "Solo las tareas completadas o fallidas pueden reiniciarse", 500 
    logger.info(f"restarting task {id}")
    t.status_msg = "reiniciando..."
    t.current_step = 'compilator'
    t.step_state = 0
    db.session.commit()
    return f"Tarea {id} reiniciada exitosamente", 200

def retry_last_step(id):

    t = Task.query.get(id)
    if not t:
        return f"La tarea {id} no existe", 500    
    if not t.step_state in [-1,2]:
        return "Solo las tareas completadas o fallidas pueden modificarse", 500
    if t.current_step == 'compilator':
        return restart_task(id)
    logger.info(f"retrying step for task {id}")
    t.status_msg = "Reintentando..."
    t.step_state = 1 
    db.session.commit()
    return f"Reintentando el último paso de la tarea {id} ", 200

def delete_finished():    

    tasks = Task.query.filter_by(step_state = 2).all()
    logger.info(f"deleting {len(tasks)} finished tasks")        
    processing_thread = threading.Thread(target = delete_finished_background, 
                                            args = (tasks,), name = 'delete_finished_thread')   
    for t in tasks:
        t.visible = False
        db.session.commit()
    db.session.close()
    processing_thread.start()
    return "Las tareas finalizadas están siendo eliminadas en segundo plano", 200

def delete_finished_background(tasks):    
    with application.app_context():
        for t in tasks:
            try:
                if t.step_state == 2:
                    db.session.delete(t)
                    db.session.commit()        
            except Exception as e:
                t.visible = True
                db.session.commit()
                logger.error("Error occurred when trying to delete finished tasks")
                logger.error(traceback.format_exc())    
        clear_database()

def delete_failed():

    tasks = Task.query.filter_by(step_state = -1).all()
    logger.info(f"deleting {len(tasks)} failed tasks")
    processing_thread = threading.Thread(target = delete_failed_background, 
                                            args = (tasks,), name = 'delete_failed_thread')   
    for t in tasks:
        t.visible = False
        db.session.commit()
    db.session.close()
    processing_thread.start()
    return "Las tareas fallidas están siendo eliminadas en segundo plano", 200
    
def delete_failed_background(tasks):
    with application.app_context():
        for t in tasks:
            try:
                if t.step_state == -1:
                    db.session.delete(t)
                    db.session.commit()        
            except Exception as e:
                t.visible = True
                db.session.commit()
                logger.error("Error occurred when trying to delete failed tasks")
                logger.error(traceback.format_exc())
        clear_database()

def clear_database():

    # Clear series with no tasks associated
    series = Series.query.all()
    for ss in series:
        try:
            if not ss.tasks.first() and not ss.originating_task:
                logger.info(f'deleting empty series {ss}')
                db.session.delete(ss)
                db.session.commit()
        except Exception as e:
                logger.error(f'error when deleting empty series {ss}')
                logger.error(traceback.format_exc())

    # Clear orphan instances:
    for instance in Instance.query.filter_by(series = None).all():
        try:
            logger.info(f'deleting orphan instance {instance}')
            db.session.delete(instance)
            db.session.commit()
        except Exception as e:
            logger.error(f'error when deleting instance {instance}')
            logger.error(traceback.format_exc())
    
    # Clear studies with no series
    studies = Study.query.all()
    for st in studies:
        try:
            if not st.series.first():
                logger.info(f'deleting empty study {st}')
                db.session.delete(st)
                db.session.commit()
        except Exception as e:
                logger.error(f'error when deleting empty study {st}')
                logger.error(traceback.format_exc())

    # Clear patients with no studies
    patients = Patient.query.all()
    for pt in patients:
        try:
            if not pt.series.first():
                logger.info(f'deleting empty patient {pt}')
                db.session.delete(pt)
                db.session.commit()
        except:
                logger.error(f'error when deleting empty patient {pt}')
                logger.error(traceback.format_exc())
    
    # Delete files with no corresponding database objects
    clear_storage()
    
def clear_storage():
    studies = os.listdir('incoming')
    for st in studies:
        st_path = os.path.join('incoming', st)
        st_db = Study.query.filter_by(stored_in = st_path).first()
        if not st_db:
            logger.info(f'Deleting non-db study {st_path}')
            rmtree(st_path)
        else:            
            series = os.listdir(st_path)
            for ss in series:
                ss_path = os.path.join(st_path, ss)
                ss_db = Series.query.filter_by(stored_in = ss_path).first()
                if not ss_db:
                    logger.info(f'Deleting non-db series {ss_path}')     
                    rmtree(ss_path)


    
