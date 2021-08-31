class Model(object):
    def __init__(self, object_id, name, created, ver_date):
        self._object_id = object_id
        self._name = name
        self._created = created
        self._ver_date = ver_date

    @property
    def id(self):
        return self._object_id

    name = property(lambda self: self._name)
    created = property(lambda self: self._created)
    last_modified = property(lambda self: self._ver_date)
