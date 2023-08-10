target_series_uid = '1.2.840.113619.2.290.3.1460327308.853.1690804879.484'
target_instance_uid = '1.2.840.113619.2.290.1460327308.1691005072.793312'
target_source_addr = '10.87.140.41'

tasks_query = (
    Task.query.
    filter_by(source_addr=target_source_addr).
    join(Series).
    filter_by(SeriesInstanceUID = target_series_uid).
    outerjoin(task_instance).
    outerjoin(Instance).
    filter(Instance.SOPInstanceUID != target_instance_uid)
)
"""
    Task.query
    .join(Series)
    .outerjoin(Instance)
    .filter(Series.SeriesInstanceUID == target_series_uid)
    .filter(Task.source_addr == target_source_addr)
    .all()
)
"""

print(tasks_query)