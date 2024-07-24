import logging
from app_pkg import db
from app_pkg.db_models import Task

logger = logging.getLogger('__main__')

def delete_task(id):

    t = Task.query.get(id)
    if not t:
        return f"Task {id} doesn't exist", 500    
    if not t.step_state in [-1,2]:
        return "Only completed or failed tasks can be deleted", 500    
    
    logger.info(f"trying to delete task {id}")
    db.session.delete(t)
    db.session.commit()
    return f"Task {id} deleted succesfully", 200

def restart_task(id):

    t = Task.query.get(id)
    if not t:
        return f"Task {id} doesn't exist", 500     
    if not t.step_state in [-1,2]:
        return "Only completed or failed tasks can be restarted", 500 
    logger.info(f"restarting task {id}")
    t.status_msg = "restarting..."
    t.current_step = 'compilator'
    t.step_state = 0
    db.session.commit()
    return f"Task {id} restarted succesfully", 200

def retry_last_step(id):

    t = Task.query.get(id)
    if not t:
        return f"Task {id} doesn't exist", 500    
    if not t.step_state in [-1,2]:
        return "Only completed or failed tasks can be modified", 500
    if t.current_step == 'compilator':
        return restart_task(id)
    logger.info(f"retrying step for task {id}")
    t.status_msg = "retrying..."
    t.step_state = 1 
    db.session.commit()
    return f"Retrying last step for task {id} ", 200

def delete_finished():

    tasks = Task.query.filter_by(step_state = 2).all()
    logger.info(f"deleting {len(tasks)} finished tasks")
    try:
        for t in tasks:
            db.session.delete(t)
            db.session.commit()
        return f"{len(tasks)} finished tasks deleted successfully ", 200
    except:
        return "Uknown error occurred when trying to delete finished tasks", 500

def delete_failed():

    tasks = Task.query.filter_by(step_state = -1).all()
    logger.info(f"deleting {len(tasks)} failed tasks")
    try:
        for t in tasks:
            db.session.delete(t)
        db.session.commit()
        return f"{len(tasks)} failed tasks deleted successfully ", 200
    except:
        return "Uknown error occurred when trying to delete failed tasks", 500

