target_series_uid = '1.2.840.113619.2.290.3.1460327308.171.1691409638.99'
target_instance_uid = '1.2.840.10008.5.1.4.1.1.128'

tasks_query = (
    Task.query
    .join(Series)
    .outerjoin(Instance, Instance.SeriesInstanceUID == Series.SeriesInstanceUID)
    .filter(Series.SeriesInstanceUID == target_series_uid)
    .filter(Instance.SOPInstanceUID != target_instance_uid)
    .all()
)

print('done')