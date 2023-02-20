import json
import re
from urllib.request import urlopen

object_keys = ["properties", "required", "additionalProperties", "minProperties", "maxProperties", "dependencies",
               "patternProperties"]
"""Object schema keywords."""

array_keys = ["items", "additionalItems", "minItems", "maxItems", "uniqueItems"]
"""Array schema keywords."""

string_keys = ["minLength", "maxLength", "pattern", "format"]
"""String schema keywords."""

numeric_keys = ["multipleOf", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"]


class Schema:
    """ Base class for all schemas."""

    def __init__(self, s, d_schema, path, definitions):
        """
        :param s: schema as a python dict object.
        :param d_schema: the whole first schema.
        :param path: the path that was used to call this schema inside a $ref (can be an empty string if it was not
        called from a $ref).
        :param definitions: integer that indicates where inside `definitions` are this schema definitions.
        :return: None.
        """

        self.definitions = definitions
        if path != "":
            self.definitions[path] = self
        self.dict = s
        self.path = path
        """A string that holds the referenced used to point at this schema (may be an empty string."""

        self.type = None
        """The type (or types) of the schema if there is any."""

        self.enum = []
        """TODO: describir el enum. """

        if has_key(s, "type"):
            self.type = s['type']
        self.multiple_types = []
        """If there is more than one type for this schema, this list will hold each type's schema object."""

        if has_key(s, "enum"):
            self.enum = s['enum']
        self.allOf = []
        """A list that holds all the schema objects which json documents must be valid against."""

        if has_key(s, "allOf"):
            for schema in s["allOf"]:
                self.allOf.append(get_schema2(schema, d_schema, "", self.definitions))
        self.oneOf = []
        """A list that holds schemas. A json document must be valid against only one of these."""
        if has_key(s, "oneOf"):
            for element in s["oneOf"]:
                self.oneOf.append(get_schema2(element, d_schema, "", self.definitions))
        self.anyOf = []
        """A list that holds schemas. A json document must be valid at least against one of these."""

        if has_key(s, "anyOf"):
            for element in s["anyOf"]:
                self.anyOf.append(get_schema2(element, d_schema, "", self.definitions))
        self.n = []
        """ A list that holds schemas. A json document must not be valid against all of these"""

        if has_key(s, "not"):
            for element in s["not"]:
                self.n.append(get_schema2(element, d_schema, "", self.definitions))

    def validate(self, j):
        """
        This method is used to validate base schema properties (enum, allOf, oneOf, not, anyOf) and schemas that have
        multiple types.
        :param j: Document to validate against this schema.
        :return: `Response` object.
        """

        if len(self.multiple_types) > 0:
            valid = False
            for schema in self.multiple_types:
                if isinstance(j, get_class(schema.type)) or (j is None and schema.type == "null"):
                    r = schema.validate(j)
                    if not r.b:
                        return Response(False, r.message, r.schema_nodes, r.document_nodes)
                    valid = True
            if not valid:
                return Response(False, "\nFailed type on:\n" + str(json.dumps(j, indent=2)) + "\n(must be one of: " +
                                str(self.type), ["type"], [])
        for schema in self.allOf:
            r = schema.validate(j)
            if not r.b:
                r.schema_nodes.insert(0, self.allOf.index(schema))
                r.schema_nodes.insert(0, "allOf")
                return Response(False, "\nFailed allOf on: \n" + str(json.dumps(j, indent=2)) + "\n" + r.message,
                                r.schema_nodes, r.document_nodes)
        if self.anyOf:
            validated = False
            for schema in self.anyOf:
                r = schema.validate(j)
                if r.b:
                    validated = True
            if not validated:
                return Response(False, "\nFailed anyOf on: \n" + str(json.dumps(j, indent=2)), ["anyOf"],
                                [])
        if self.oneOf:
            count = 0
            for schema in self.oneOf:
                if schema.validate(j).b:
                    count += 1
            if count > 1:
                return Response(False, "\nFailed oneOf (Validates against more than one) on: \n" +
                                str(json.dumps(j, indent=2)), ["oneOf"], [])
            elif count == 0:
                return Response(False, "\nFailed oneOf (Validates against none) on: \n" + str(json.dumps(j, indent=2)),
                                ["oneOf"], [])
        for schema in self.n:
            r = schema.validate(j)
            if r.b:
                return Response(False, "\nFailed not on: \n" + str(json.dumps(j, indent=2)) + "\n",
                                ["not", self.n.index(schema)], [])
        if len(self.enum) > 0:
            validated = False
            for object_in_enum in self.enum:
                if j == object_in_enum:
                    validated = True
            if not validated:
                return Response(False, "\nFailed enum on: \n" + str(json.dumps(j, indent=2)) +
                                "\n(valid values:" + str(self.enum) + ")", ["enum"], [])
        return Response(True, "", [], [])


class ObjectSchema(Schema):
    """Object schema's class"""

    def __init__(self, s, d_schema, path, index):
        """
        :param s: schema as a python dict object.
        :param d_schema: the whole first schema.
        :param path: the path that was used to call this schema inside a $ref (can be an empty string if it was not
        called from a $ref).
        :param index: integer that indicates where inside `definitions` are this schema definitions.
        :return: None.
        """

        super().__init__(s, d_schema, path, index)
        self.required = {}
        """Dict object where each required key of a schema holds its schema."""

        self.properties = {}
        """Dict object where each not-required key of a schema holds its schema."""

        self.minProperties = None
        """Minimum number of properties that a json_document must have."""

        self.maxProperties = None
        """Maximum number of properties that a json_document must have."""

        self.property_dependencies = {}
        """Dict object where each key holds the list of the properties that a json document must have if that key is
        also there."""

        self.schema_dependencies = {}
        """Dict object where each key holds the schema that a json document must be valid against if the document contains
        that key."""

        self.patternProperties = {}
        """Dict where each key corresponds to a pattern and each key hold a schema that every json object's key
        that correspond to that pattern must be valid against."""

        self.additionalProperties = "default"
        """If it's a schema, every property that's not inside `self.properties` and `self.required` must be
        valid against it. If it's a boolean, if it's False, a json document can not have any additional property."""

        if has_key(s, "additionalProperties"):
            if isinstance(s["additionalProperties"], dict):
                self.additionalProperties = get_schema2(s["additionalProperties"], d_schema, "", self.definitions)
            else:
                self.additionalProperties = s["additionalProperties"]
        if has_key(s, "minProperties"):
            self.minProperties = s["minProperties"]
        if has_key(s, "maxProperties"):
            self.maxProperties = s["maxProperties"]
        if has_key(s, "properties"):
            for key in s['properties']:
                if has_key(s, "required"):
                    if s['required'].count(key) == 1:
                        self.required[key] = get_schema2(s['properties'][key], d_schema, "", self.definitions)
                    else:
                        self.properties[key] = get_schema2(s['properties'][key], d_schema, "", self.definitions)
                else:
                    self.properties[key] = get_schema2(s['properties'][key], d_schema, "", self.definitions)
        if has_key(s, "required"):
            for prop in s['required']:
                if not has_key(self.required, prop):
                    self.required[prop] = get_schema2({}, d_schema, "", self.definitions)
        if has_key(s, "dependencies"):
            for key in s["dependencies"]:
                # schema_dependencies es un diccionario si una llave se encuentra en las properties de un objeto
                # entonces el objeto debe ser valido ante este esquema.
                if isinstance(s["dependencies"][key], dict):
                    self.schema_dependencies[key] = get_schema2(s["dependencies"][key], d_schema, "", self.definitions)
                # property_dependencies es un diccionario que si una llave se encuentra en las properties de
                # un objeto, entonces todos los strings en la lista correspondiente a esa key deben estar dentro de
                # las propiedades de dicho objeto
                else:
                    self.property_dependencies[key] = s["dependencies"][key]
        if has_key(s, 'patternProperties'):
            for key in s['patternProperties']:
                self.patternProperties[key] = get_schema2(s['patternProperties'][key], d_schema, "", self.definitions)

    def validate(self, document):
        """
        This method is used to validate object schema properties.
        :param document: Document to validate against this schema.
        :return: `Response` object.
        """

        validate_base_schema = super().validate(document)
        if not validate_base_schema.b:
            return Response(False, "\nFailed objectSchema on:\n" + str(json.dumps(document, indent=2)) + "\n" + validate_base_schema.message,
                            validate_base_schema.schema_nodes, validate_base_schema.document_nodes)
        if not isinstance(document, dict):
            return Response(False, "\nFailed type on:\n" + str(json.dumps(document, indent=2)) + "\n(must be type object)",
                            ["type"], [])
        used_dependencies = self.get_used_schema_dependencies(document)
        for key in used_dependencies:
            validate_base_schema = used_dependencies[key].validate(document)
            if not validate_base_schema.b:
                validate_base_schema.schema_nodes.insert(0, key)
                validate_base_schema.schema_nodes.insert(0, "dependencies")
                return Response(False, "\nFailed schemaDependency on: \n" + str(json.dumps(document, indent=2))
                                + "\n" + validate_base_schema.message, validate_base_schema.schema_nodes, validate_base_schema.document_nodes)
        if isinstance(self.additionalProperties, bool) or isinstance(self.additionalProperties, str):
            if not self.additionalProperties:
                for key in document:
                    if not has_key(self.required, key) and not has_key(self.properties, key) \
                            and not self.is_valid_pattern(key):
                        return Response(False, "\nFailed additionalProperty on: \n" + str(json.dumps(document, indent=2)) +
                                        "\n(additionalProperties are not allowed)\n(additional key: " + key + ")",
                                        ["additionalProperties"], [key])
        elif isinstance(self.additionalProperties, dict):
            for key in document:
                if not has_key(self.required, key) and not has_key(self.properties, key) \
                        and not self.is_valid_pattern(key):
                    validate_base_schema = self.additionalProperties.validate(document[key])
                    if not validate_base_schema.b:
                        validate_base_schema.schema_nodes.insert(0, "additionalProperties")
                        validate_base_schema.document_nodes.insert(0, key)
                        return Response(False, "\nFailed additionalProperty on: \n" + str(json.dumps(document, indent=2)) +
                                        " key: " + key + "\n" + validate_base_schema.message, validate_base_schema.schema_nodes, validate_base_schema.document_nodes)
        for key in self.required:
            if not has_key(document, key):
                # TODO: Acordarse del indice de required?
                return Response(False, "\nFailed requiredProperty on:\n" + str(json.dumps(document, indent=2)) +
                                "\n(missing required property: " + key + ")", ["required", key], [])
            else:
                validate_base_schema = self.required[key].validate(document[key])
                if not validate_base_schema.b:
                    validate_base_schema.schema_nodes.insert(0, key)
                    validate_base_schema.schema_nodes.insert(0, "properties")
                    validate_base_schema.document_nodes.insert(0, key)
                    return Response(False, "\nFailed requiredProperty on:\n" + str(json.dumps(document, indent=2)) + "\n(key: "
                                    + key + ")\n" + validate_base_schema.message, validate_base_schema.schema_nodes, validate_base_schema.document_nodes)
        for key in self.properties:
            if has_key(document, key):
                validate_base_schema = self.properties[key].validate(document[key])
                if not validate_base_schema.b:
                    validate_base_schema.schema_nodes.insert(0, key)
                    validate_base_schema.schema_nodes.insert(0, "properties")
                    validate_base_schema.document_nodes.insert(0, key)
                    return Response(False, "\nFailed property on:\n" + str(json.dumps(document, indent=2)) + "\n(key: " + key +
                                    ")\n" + validate_base_schema.message, validate_base_schema.schema_nodes, validate_base_schema.document_nodes)
        if self.minProperties is not None:
            if len(document) < self.minProperties:
                return Response(False, "\nFailed minProperties on:\n" + str(json.dumps(document, indent=2)) + "\n(minimum is "
                                + str(self.minProperties) + ")", ["minProperties"], [])
        if self.maxProperties is not None:
            if len(document) > self.maxProperties:
                return Response(False, "\nFailed maxProperties on:\n" + str(json.dumps(document, indent=2)) + "\n(maximum is "
                                + str(self.maxProperties) + ")", ["maxProperties"], [])
        for key in self.property_dependencies:
            if has_key(document, key):
                if isinstance(self.property_dependencies[key], str):
                    if not has_key(document, self.property_dependencies[key]):
                        return Response(False, "\nFailed dependency on:\n" + str(json.dumps(document, indent=2)) +
                                        "\n(missing required key: " + self.property_dependencies[key] + ")",
                                        ["dependencies", key], [])
                else:
                    for key2 in self.property_dependencies[key]:
                        if not has_key(document, key2):
                            return Response(False, "\nFailed dependency on:\n" + str(json.dumps(document, indent=2)) +
                                            "\n(missing required key: " + self.property_dependencies[key][key2] + ")",
                                            ["dependencies", key], [])
        # patternProperties que se sobrelapan con properties?
        for key in document:
            for key2 in self.patternProperties:
                if check_pattern(key2, key):
                    validate_base_schema = self.patternProperties[key2].validate(document[key])
                    if not validate_base_schema.b:
                        validate_base_schema.schema_nodes.insert(0, key2)
                        validate_base_schema.schema_nodes.insert(0, "patternProperties")
                        validate_base_schema.document_nodes.insert(0, key)
                        return Response(False, "\nFailed patternProperty on:\n" + str(json.dumps(document, indent=2)) +
                                        "\n(key: " + key + ")\n" + validate_base_schema.message, validate_base_schema.schema_nodes, validate_base_schema.document_nodes)
        return Response(True, "", [], [])

    def is_valid_pattern(self, key):
        """
        Verifies whether this key matches any pattern defined insite `self.patternProperties`.
        :param key: string.
        :return: boolean.
        """

        for patternKey in self.patternProperties:
            if check_pattern(patternKey, key):
                return True
        if self.additional_properties_allowed():
            return True
        else:
            return False

    def additional_properties_allowed(self):
        if (isinstance(self.additionalProperties, bool) and self.additionalProperties) or \
                (isinstance(self.additionalProperties, str)):
            return True
        else:
            return False

    def get_used_schema_dependencies(self, document):
        """
        Makes a list that holds every schema that the json document `j` must be valid against based on the schema's
        dependencies.
        :param document: json document.
        :return: List of schemas.
        """

        used_dependencies = {}
        for key in document:
            if has_key(self.schema_dependencies, key):
                used_dependencies[key] = self.schema_dependencies[key]
        return used_dependencies


class StringSchema(Schema):
    """
    String schema class.
    """

    def __init__(self, s, d_schema, path, index):
        """
        :param s: schema as a python dict object.
        :param d_schema: the whole first schema.
        :param path: the path that was used to call this schema inside a $ref (can be an empty string if it was not
        called from a $ref).
        :param index: integer that indicates where inside `definitions` are this schema definitions.
        :return: None.
        """

        super().__init__(s, d_schema, path, index)
        self.format = ""

    def validate(self, j):
        """
        This method is used to validate string schema properties.
        :param j: Document to validate against this schema.
        :return: `Response` object.
        """

        r = super().validate(j)
        if not r.b:
            return Response(False, "\nFailed StringSchema on:\n" + str(json.dumps(j, indent=2)) + "\n" + r.message,
                            r.schema_nodes, r.document_nodes)
        if not isinstance(j, str):
            return Response(False, "\nFailed type on:\n" + str(json.dumps(j, indent=2)) + "\n(must be type string)",
                            ["type"], [])
        return Response(True, "", [], [])


class IntegerSchema(Schema):
    """
    Integer schema class.
    """

    def __init__(self, s, d_schema, path, index):
        """
        :param s: schema as a python dict object.
        :param d_schema: the whole first schema.
        :param path: the path that was used to call this schema inside a $ref (can be an empty string if it was not
        called from a $ref).
        :param index: integer that indicates where inside `definitions` are this schema definitions.
        :return: None.
        """

        super().__init__(s, d_schema, path, index)

    def validate(self, j):
        """
        This method is used to validate integer schema properties.
        :param j: Document to validate against this schema.
        :return: `Response` object.
        """

        r = super().validate(j)
        if not r.b:
            return Response(False, "\nFailed IntegerSchema on:\n" + str(json.dumps(j, indent=2)) + "\n" + r.message,
                            r.schema_nodes, r.document_nodes)
        if isinstance(j, bool):
            return Response(False, "\nFailed type on:\n" + str(json.dumps(j, indent=2)) + "\n(must be type int)",
                            ["type"], [])
        if not isinstance(j, int):
            return Response(False, "\nFailed type on:\n" + str(j) + "\n(must be type int)", ["type"], [])
        return Response(True, "", [], [])


class NumberSchema(Schema):
    """
    Number schema class.
    Yo estoy en esto (Antonia)
    """

    def __init__(self, s, d_schema, path, index):
        """
        :param s: schema as a python dict object.
        :param d_schema: the whole first schema.
        :param path: the path that was used to call this schema inside a $ref (can be an empty string if it was not
        called from a $ref).
        :param index: integer that indicates where inside `definitions` are this schema definitions.
        :return: None.
        """
        super().__init__(s, d_schema, path, index)

    def validate(self, j):
        """
        This method is used to validate number schema properties.
        :param j: Document to validate against this schema.
        :return: `Response` object.
        """

        r = super().validate(j)
        if not r.b:
            return Response(False, "\nFailed NumberSchema on:\n" + str(json.dumps(j, indent=2)) + "\n" + r.message,
                            r.schema_nodes, r.document_nodes)
        if isinstance(j, bool):
            return Response(False, "\nFailed type on:\n" + str(json.dumps(j, indent=2)) + "\n(must be type float)",
                            ["type"], [])
        if not isinstance(j, float):
            return Response(False, "\nFailed type on:\n" + str(json.dumps(j, indent=2)) + "\n(must be type float)",
                            ["type"], [])
        return Response(True, "", [], [])


class BooleanSchema(Schema):
    """
    Boolean schema class.
    """

    def __init__(self, s, d_schema, path, index):
        """
        :param s: schema as a python dict object.
        :param d_schema: the whole first schema.
        :param path: the path that was used to call this schema inside a $ref (can be an empty string if it was not
        called from a $ref).
        :param index: integer that indicates where inside `definitions` are this schema definitions.
        :return: None.
        """

        super().__init__(s, d_schema, path, index)

    def validate(self, j):
        """
        This method is used to validate boolean schema properties.
        :param j: Document to validate against this schema.
        :return: `Response` object.
        """

        r = super().validate(j)
        if not r.b:
            return Response(False, "\nFailed StringSchema on:\n" + str(json.dumps(j, indent=2)) + "\n" + r.message,
                            r.schema_nodes, r.document_nodes)
        if not isinstance(j, bool):
            return Response(False, "\nFailed type on:\n" + str(json.dumps(j, indent=2)) + "\n(must be type bool)",
                            ["type"], [])
        return Response(True, "", [], [])


class ArraySchema(Schema):
    """
    Array schema class.
    """

    def __init__(self, s, d_schema, path, index):
        """
        :param s: schema as a python dict object.
        :param d_schema: the whole first schema.
        :param path: the path that was used to call this schema inside a $ref (can be an empty string if it was not
        called from a $ref).
        :param index: integer that indicates where inside `definitions` are this schema definitions.
        :return: None.
        """

        super().__init__(s, d_schema, path, index)
        self.items = "default"
        """List or schema or a schema."""

        self.additionalItems = Schema({}, {}, "", self.definitions)
        """Schema or boolean."""

        self.maxItems = None
        """Number of maximum items that a json array must have."""

        self.minItems = None
        """Number of minimum items that a json array must have."""

        self.uniqueItems = False
        """Whether or not an array must have unique items."""

        if has_key(s, "items"):
            if isinstance(s["items"], list):
                for element in s["items"]:
                    self.items.append(get_schema2(element, d_schema, "", self.definitions))
            else:
                self.items = get_schema2(s["items"], d_schema, "", self.definitions)
        if has_key(s, "additionalItems"):
            self.additionalItems = get_schema2(s["additionalItems"], d_schema, "", self.definitions)
        if has_key(s, "maxItems"):
            self.maxItems = s["maxItems"]
        if has_key(s, "minItems"):
            self.minItems = s["minItems"]
        if has_key(s, "uniqueItems"):
            self.uniqueItems = s["uniqueItems"]

    def validate(self, j):
        """
        This method is used to validate array schema properties.
        :param j: Document to validate against this schema.
        :return: `Response` object.
        """

        r = super().validate(j)
        if not r.b:
            return Response(False, "\nFailed StringSchema on:\n" + str(json.dumps(j, indent=2)) + "\n" + r.message,
                            r.schema_nodes, r.document_nodes)
        if not isinstance(j, list):
            return Response(False, "\nFailed type on:\n" + str(json.dumps(j, indent=2)) + "\n(must be type list)",
                            ["type"], [])
        if isinstance(self.items, list):
            length2 = 0
            if len(j) >= len(self.items):
                length = len(self.items)
                length2 = len(j)
            else:
                length = len(j)
            for index in range(0, length):
                r = self.items[index].validate(j[index])
                if not r.b:
                    r.schema_nodes.insert(0, index)
                    r.schema_nodes.insert(0, "items")
                    r.document_nodes.insert(0, index)
                    return Response(False, "\nFailed item at index " + str(index) + " on:\n" +
                                    str(json.dumps(j, indent=2)) + "\n" + r.message, r.schema_nodes, r.document_nodes)
            if length2 != 0:
                for index in range(length, length2):
                    r = self.additionalItems.validate(j[index])
                    if not r.b:
                        r.schema_nodes.insert(0, index)
                        r.schema_nodes.insert(0, "additionalItems")
                        r.document_nodes.insert(0, index)
                        return Response(False, "\nFailed additionalItem on:\n" + str(json.dumps(j, indent=2)) + "\n"
                                        + r.message, r.schema_nodes, r.document_nodes)
        else:
            for index in range(0, len(j)):
                r = self.items.validate(j[index])
                if not r.b:
                    r.schema_nodes.insert(0, "items")
                    r.document_nodes.insert(0, index)
                    return Response(False, "\nFailed item on:\n" + str(json.dumps(j, indent=2)) + "\n" + r.message,
                                    r.schema_nodes, r.document_nodes)
        if self.maxItems is not None:
            if len(j) > self.maxItems:
                return Response(False, "\nFailed maxItems on:\n" + str(json.dumps(j, indent=2)) +
                                "\n(size is greater than " + str(self.maxItems) + ")", ["maxItems"], [])
        if self.minItems is not None:
            if len(j) < self.minItems:
                return Response(False, "\nFailed minItems on:\n" + str(json.dumps(j, indent=2)) +
                                "\n(size is smaller than " + str(self.minItems) + ")", ["minItems"], [])
        if self.uniqueItems:
            for index in range(0, len(j)):
                if j.count(j[index]) > 1:
                    return Response(False, "\nFailed uniqueItems on:\n" + str(json.dumps(j, indent=2))
                                    + "\nrepeated item:\n" + json.dumps(j[index], indent=2), ["uniqueItems"], [index])
        return Response(True, "", [], [])


class NullSchema(Schema):
    """
    Null schema class.
    """

    def __init__(self, s, d_schema, path, index):
        """
        :param s: schema as a python dict object.
        :param d_schema: the whole first schema.
        :param path: the path that was used to call this schema inside a $ref (can be an empty string if it was not
        called from a $ref).
        :param index: integer that indicates where inside `definitions` are this schema definitions.
        :return: None.
        """

        super().__init__(s, d_schema, path, index)

    def validate(self, j):
        """
        :param j: Document to validate against this schema.
        :return: `Response` object.
        """

        r = super().validate(j)
        if not r.b:
            return Response(False, "\nFailed StringSchema on:\n" + str(json.dumps(j, indent=2)) + "\n" + r.message,
                            r.schema_nodes, r.document_nodes)
        if not isinstance(j, list):
            return Response(False, "\nFailed type on:\n" + str(json.dumps(j, indent=2)) + "\n(must be None)", ["type"],
                            [])
        return Response(True, "", [], [])


class Response:
    """
    The result of validating a document against a schema.
    """

    def __init__(self, b, message, schema_nodes, document_nodes):
        """
        :param b: True if the document is valid or Flase if it's not valid.
        :param message: Message with a detailed description of what failed if it failed.
        :param schema_nodes: A list that holds each node of the schema that failed.
        :param document_nodes: A list that holds each node of the document that failed.
        :return: None.
        """

        self.b = b
        self.message = message
        self.schema_nodes = schema_nodes
        self.document_nodes = document_nodes

    def __repr__(self):
        """
        :return:String representation of the response.
        """

        if self.b:
            return "Valid schema"
        else:
            return "Invalid Schema: " + self.message



# Este metodo recibe un diccionario y retorna un objeto schema correspondiente, con las definiciones ya construidas
# ESTE METODO SOLO DEBE LLAMARSE DENTRO DE LAS CLASES OBJECTSCHEMA Y ARRAYSCHEMA!!! para obtener un schema a partir
# de un diccionario sin definiciones construidas se debe usar el metodo get_schema!
def get_dict_from_uri(uri):
    """
    Resolves uris.
    :param uri: URI string pointing to a schema.
    :return: corresponding schema.
    """
    # TODO: mejorar la diferenciación entre uri y local file's paths
    if uri[0:4] == "http":
        return get_dict_from_id(uri)
    else:
        return load_schema_from_file(uri)


def get_schema2(s, d_schema, path, definitions):
    """
    The method that should be called from inside a schema to obtain a child schema of that schema. (so many schemas!)
    :param s: Dict that represents the schema.
    :param d_schema: The whole schema.
    :param path: The URI or JSONPointer that was used to point at this schema.
    :param definitions: Integer that indicates where inside `definitions` are this schema definitions.
    :return: A corresponding schema class.
    """

    if has_key(s, "$ref"):
        if has_key(definitions, s['$ref']):
            return definitions[s['$ref']]
        if s["$ref"][0] == "#":
            return get_schema2(go_to(s['$ref'], d_schema), d_schema, s['$ref'], definitions)
        else:
            d = get_dict_from_uri(s["$ref"])
            return get_schema2(d, d, "", {})
    t = infer_type(s)
    if isinstance(t, str):
        if t == 'object':
            return ObjectSchema(s, d_schema, path, definitions)
        elif t == 'integer':
            return IntegerSchema(s, d_schema, path, definitions)
        elif t == 'number':
            return NumberSchema(s, d_schema, path, definitions)
        elif t == 'string':
            return StringSchema(s, d_schema, path, definitions)
        elif t == 'boolean':
            return BooleanSchema(s, d_schema, path, definitions)
        elif t == 'array':
            return ArraySchema(s, d_schema, path, definitions)
        elif t == 'null':
            return NullSchema(s, d_schema, path, definitions)
        else:
            return Schema(s, d_schema, path, definitions)
    else:
        r = Schema(s, d_schema, path, definitions)
        for type_ in t:
            if type_ == 'object':
                ap = ObjectSchema(s, d_schema, "", definitions)
                ap.type = "object"
                r.multiple_types.append(ap)
            elif type_ == 'integer':
                ap = IntegerSchema(s, d_schema, "", definitions)
                ap.type = "integer"
                r.multiple_types.append(ap)
            elif type_ == 'number':
                ap = NumberSchema(s, d_schema, "", definitions)
                ap.type = "number"
                r.multiple_types.append(ap)
            elif type_ == 'string':
                ap = StringSchema(s, d_schema, "", definitions)
                ap.type = "string"
                r.multiple_types.append(ap)
            elif t == 'boolean':
                ap = BooleanSchema(s, d_schema, "", definitions)
                ap.type = "boolean"
                r.multiple_types.append(ap)
            elif t == 'array':
                ap = ArraySchema(s, d_schema, "", definitions)
                ap.type = "array"
                r.multiple_types.append(ap)
            elif t == 'null':
                ap = NullSchema(s, d_schema, "", definitions)
                ap.type = "null"
                r.multiple_types.append(ap)
        return r


# Este es el metodo principal para obtener un schema en base a un diccionario. Arma todas las definiciones referidas
# dentro del schema (si hay definiciones que no se usan estas no se construyen).
def get_schema(s):
    """
    The method that should be called from outside a schema to obtain the whole schema object.
    :param s: Dict representing a schema.
    :return: Corresponding schema class.
    """

    if has_key(s, "$ref"):
        if s["$ref"][0] == "#":
            return get_schema2(go_to(s['$ref'], s), s, s["$ref"], {})
        else:
            return get_schema(get_dict_from_id(s["$ref"]))
    t = infer_type(s)
    if isinstance(t, str):
        if t == 'object':
            return ObjectSchema(s, s, "#", {})
        elif t == 'integer':
            return IntegerSchema(s, s, "#", {})
        elif t == 'number':
            return NumberSchema(s, s, "#", {})
        elif t == 'string':
            return StringSchema(s, s, "#", {})
        elif t == 'boolean':
            return BooleanSchema(s, s, "#", {})
        elif t == 'array':
            return ArraySchema(s, s, "#", {})
        elif t == 'null':
            return NullSchema(s, s, "#", {})
        else:
            return Schema(s, s, "#", {})
    else:
        r = Schema(s, s, "#", {})
        for type_ in t:
            if type_ == 'object':
                ap = ObjectSchema(s, s, "", {})
                ap.type = "object"
                r.multiple_types.append(ap)
            elif type_ == 'integer':
                ap = IntegerSchema(s, s, "", {})
                ap.type = "integer"
                r.multiple_types.append(ap)
            elif type_ == 'number':
                ap = NumberSchema(s, s, "", {})
                ap.type = "number"
                r.multiple_types.append(ap)
            elif type_ == 'string':
                ap = StringSchema(s, s, "", {})
                ap.type = "string"
                r.multiple_types.append(ap)
            elif t == 'boolean':
                ap = BooleanSchema(s, s, "", {})
                ap.type = "boolean"
                r.multiple_types.append(ap)
            elif t == 'array':
                ap = ArraySchema(s, s, "", {})
                ap.type = "array"
                r.multiple_types.append(ap)
            elif t == 'null':
                ap = NullSchema(s, s, "", {})
                ap.type = "null"
                r.multiple_types.append(ap)
        return r


# Este metodo retorna si el diccionario d contiene la llave k
def has_key(d, k):
    """
    :param d: Dict.
    :param k: Key.
    :return:Whether the dict has this key.
    """

    if list(d.keys()).count(k) == 1:
        return True
    else:
        return False


def load_schema_from_file(path):
    """
    Loads a schema from a local file.
    :param path: Local path pointing a schema.
    :return: Corresponding schema class.
    """

    with open(path, encoding='utf-8') as jdata:
        invalid = False
        schema = {}
        s = open('schemasSchema', encoding='utf-8')
        s = json.load(s)
        schema_schema = get_schema(s)
        # if not check_json_string(str(jdata)):
        #     raise ValueError("Invalid json file (Duplicated keys) at " + path)
        try:
            schema = json.load(jdata)
        except ValueError:
            invalid = True
        if invalid:
            raise ValueError("Invalid json file at " + path)
        if not schema_schema.validate(schema).b:
            raise ValueError("Invalid schema definition at " + path)
        else:
            return get_schema(schema)


def load_json_from_file(path):
    """
    Loads a json object from a local file.
    :param path: Path to the json object.
    :return: Dict.
    """

    with open(path, encoding='utf-8') as jdata:
        # if not check_json_string(str(jdata)):
        #     raise ValueError("Invalid json file (Duplicated keys) at " + path)
        try:
            return json.load(jdata)
        except ValueError:
            pass
        raise ValueError("Invalid json file at " + path)


# Retorna el elemento que se encuentra en el string path dentro del schema diccionario.
def go_to(path, d_schema):
    """
    :param path: JSONPointer string.
    :param d_schema: Dict representing a chema.
    :return: The dict inside `d_schema` that points the JSONPointer string.
    """

    nodos = get_nodes(path)
    r = d_schema
    for nodo in nodos:
        if nodo == "#":
            continue
        else:
            if isinstance(r, list):
                r = r[int(nodo)]
            else:
                r = r[nodo]
    return r


def check_pattern(pattern, string):
    """
    :param pattern: Regular expression.
    :param string: Any string.
    :return:True if the string matches the patter.
    """

    p = re.compile(pattern)
    for index in range(0, len(string)):
        if p.match(string, index):
            return True
    return False


def check_json_string(s):
    if s[0] == "{":
        key_values = s[1:len(s) - 1].split(",")
        keys = []
        for key_value in key_values:
            k_v = key_value.split(":")
            key = k_v[0]
            value = k_v[1]
            keys.append(key)
            if keys.count(key) > 1:
                return False
            elif not check_json_string(value):
                return False
        return True
    return True


def infer_type(s):
    """
    :param s: Dict representing a schema.
    :return:String or list that corresponds to the schema's type.
    """

    if has_key(s, "type"):
        return s["type"]
    else:
        r = []
        for key in s:
            if object_keys.count(key) == 1:
                if r.count("object") == 0:
                    r.append("object")
            elif array_keys.count(key) == 1:
                if r.count("array") == 0:
                    r.append("array")
            elif string_keys.count(key) == 1:
                if r.count("string") == 0:
                    r.append("string")
            elif numeric_keys.count(key) == 1:
                if r.count("number") == 0:
                    r.append("number")
        if len(r) == 1:
            return r[0]
        elif len(r) > 1:
            return r
        else:
            return ""


def get_class(s):
    """
    :param s: A schema type.
    :return:Class object corresponding to the type.
    """

    if s == "object":
        return dict
    elif s == "string":
        return str
    elif s == "boolean":
        return bool
    elif s == "integer":
        return int
    elif s == "number":
        return float
    elif s == "array":
        return list
    elif s == "null":
        return Schema
    else:
        return


def get_nodes(s):
    """
    :param s: JSONPointer string.
    :return: List with every node inside the JSONPointer string.
    """

    j = 0
    r = []
    s_to_add = ""
    while j < len(s):
        if s[j] == "/":
            r.append(s_to_add)
            s_to_add = ""
            j += 1
        elif s[j] == "~":
            if j + 1 < len(s) and s[j + 1] == "1":
                s_to_add += "/"
                j += 2
            elif j + 1 < len(s) and s[j + 1] == "0":
                s_to_add += "~"
                j += 2
        else:
            s_to_add += s[j]
            j += 1
    r.append(s_to_add)
    return r


def get_dict_from_url(url):
    """
    :param url: URL pointing a json schema.
    :return: The dict object representing the schema referenced in the url.
    """

    f = urlopen(url)
    json_string = f.read().decode("utf-8").replace("\n", "").replace("\t", "")
    return json.loads(json_string)


def find_parent(s, d_schema):
    if isinstance(d_schema, dict):
        for key in d_schema:
            if d_schema[key] == s:
                return d_schema
            elif isinstance(d_schema[key], dict):
                parent = find_parent(s, d_schema[key])
                if parent is not None:
                    return parent
            elif isinstance(d_schema[key], list):
                for element in d_schema[key]:
                    parent = find_parent(s, element)
                    if parent is not None:
                        return parent
    elif isinstance(d_schema, list):
        for element in d_schema:
            parent = find_parent(s, element)
            if parent is not None:
                return parent


# def get_full_id(s, d_schema, base_id):
#     if s == d_schema:
#         return d_schema["id"]
#     if s["id"].count("://") == 1:
#         return s["id"]
#     if has_key(d_schema, "id"):
#         if base_id != "":
#             if d_schema["id"][0] != "#":
#                 if d_schema["id"].count("://") == 0:
#                     base_id = base_id[:base_id.rfind("/") + 1] + d_schema["id"]
#                 else:
#                     base_id = d_schema["id"]
#         else:
#             base_id = d_schema["id"]
#     for key in d_schema:
#         if d_schema[key] == s:
#             if s['id'][0] == "#":
#                 if base_id[len(base_id) - 1] == "#":
#                     return base_id[:len(base_id) - 1] + s["id"]
#                 else:
#                     return base_id + s["id"]
#             else:
#                 return base_id[:base_id.rfind("/") + 1] + s["id"]
#         elif isinstance(d_schema[key], dict):
#             r = get_full_id(s, d_schema[key], base_id)
#             if r is not None:
#                 return r
#         elif isinstance(d_schema[key], list):
#             for element in d_schema[key]:
#                 if isinstance(element, dict):
#                     r = get_full_id(s, element)
#                     if r is not None:
#                         return r


def get_dict_from_id(id_string):
    """
    Resolves the URI id and returns the corresponding dict object that the URI points to.
    :param id_string: URI string pointing a json schema.
    :return: Dict object corresponding to a json schema.
    """

    if id_string.count("#") == 1:
        url = id_string[:id_string.rfind("#") + 1]
        fragment = id_string[id_string.rfind("#"):]
    else:
        url = id_string
        fragment = ""
    d = get_dict_from_url(url)
    if fragment == "#":
        return d
    else:
        return get_fragment(fragment, d)


def get_fragment(fragment, d_schema):
    """
    :param fragment: String representing a URI fragment.
    :param d_schema: The whole schema.
    :return: A dict object corresponding to the schema referenced in the fragment.
    """

    for key in d_schema:
        if isinstance(d_schema[key], dict):
            if has_key(d_schema[key], "id"):
                if d_schema[key]["id"] == fragment:
                    return d_schema[key]
                if d_schema[key]["id"].count("://") == 1:
                    continue
            r = get_fragment(fragment, d_schema[key])
            if r is not None:
                return r
        if isinstance(d_schema[key], list):
            for element in d_schema[key]:
                r = get_fragment(fragment, element)
                if r is not None:
                    return r


#schema2 = get_schema({"$ref": "http://json-schema.org/draft-04/hyper-schema#"})
#print(schema2.validate({"type": 5}))
json_doc = load_json_from_file('schemasSchema')
schema2 = load_schema_from_file('wikidata.json')
resp = schema2.validate(json_doc)
# schema3 = get_schema({"type": "object", "required": ["name", "age"]})
# schema = load_schema_from_file("schemasSchema")
# print(schema.anyOf[0].validate({"okay": "whatever"}).schema_nodes)
# print(go_to("#/foo/0", {"foo": ["bar", "baz"]}))
# print(go_to("#/a~1b", {"a/b": "hello, I'm conflictive"}))
print(resp)
# print(resp.document_nodes)
# print(resp.schema_nodes)
