from validator.classes import *
import time

schemas_schema = get_schema_from_file("schemasSchema")
wikidata_json = get_json_from_file("wikidata.json")


print(schemas_schema.validate(wikidata_json))

wikidata_schema = get_schema(wikidata_json)

q30 = get_json_from_file("Q30.json")
q35 = get_json_from_file("Q35.json")
print("Validating Q30: {}".format(wikidata_schema.validate(q30)))
print("Validating Q35: {}".format(wikidata_schema.validate(q35)))

# time1 = time.time()
# validate = wikidata_schema.validate(q30)
# time2 = time.time()
# print("The function took {:.4f} ms".format((time2 - time1) * 1000))
# print(validate)
# time1 = time.time()
# validate = wikidata_schema.validate(q35)
# time2 = time.time()
# print("The function took {:.4f} ms".format((time2 - time1) * 1000))
# print(validate)

# ref_schema = get_schema({"$ref": "http://json-schema.org/draft-04/hyper-schema"})
#
# print(schemas_schema.validate({"type": "object", "properties": {"minProperties": 5}}))
#
# print(schemas_schema.anyOf[2].properties["properties"].additionalProperties.anyOf)


# print(ref_schema.validate(wikidata_json))
# print("Ref schema")

# ref_is_valid = ref_schema.validate({"type": 5})
# print(ref_is_valid)
# print("---------------")
# print("Enum schema")
# enum_schema = get_schema({"enum": ["1", 1]})
# enum_is_valid = enum_schema.validate(True)
# print(enum_is_valid.is_valid)
# print(enum_is_valid.schema_pointer.nodes)


