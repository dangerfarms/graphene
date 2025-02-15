from ..utils.deprecated import warn_deprecation
from ..utils.get_unbound_function import get_unbound_function
from ..utils.props import props
from .field import Field
from .objecttype import ObjectType, ObjectTypeOptions
from .utils import yank_fields_from_attrs
from .interface import Interface

# For static type checking with Mypy
MYPY = False
if MYPY:
    from .argument import Argument  # NOQA
    from typing import Dict, Type, Callable, Iterable  # NOQA


def run_validators(arguments, *args, **kwargs):
    for argument_name in arguments.keys():
        argument = arguments[argument_name]
        arg_value = kwargs[argument_name]
        for arg_input_name in arg_value.keys():
            validator_function_name = f"validate_{arg_input_name}"
            if hasattr(argument, validator_function_name):
                validator_function = argument.__getattribute__(validator_function_name)
                validator_function(arg_value[arg_input_name])


class MutationOptions(ObjectTypeOptions):
    arguments = None  # type: Dict[str, Argument]
    output = None  # type: Type[ObjectType]
    resolver = None  # type: Callable
    interfaces = ()  # type: Iterable[Type[Interface]]


class Mutation(ObjectType):
    """
    Object Type Definition (mutation field)

    Mutation is a convenience type that helps us build a Field which takes Arguments and returns a
    mutation Output ObjectType.

    .. code:: python

        from graphene import Mutation, ObjectType, String, Boolean, Field

        class CreatePerson(Mutation):
            class Arguments:
                name = String()

            ok = Boolean()
            person = Field(Person)

            def mutate(parent, info, name):
                person = Person(name=name)
                ok = True
                return CreatePerson(person=person, ok=ok)

        class Mutation(ObjectType):
            create_person = CreatePerson.Field()

    Meta class options (optional):
        output (graphene.ObjectType): Or ``Output`` inner class with attributes on Mutation class.
            Or attributes from Mutation class. Fields which can be returned from this mutation
            field.
        resolver (Callable resolver method): Or ``mutate`` method on Mutation class. Perform data
            change and return output.
        arguments (Dict[str, graphene.Argument]): Or ``Arguments`` inner class with attributes on
            Mutation class. Arguments to use for the mutation Field.
        name (str): Name of the GraphQL type (must be unique in schema). Defaults to class
            name.
        description (str): Description of the GraphQL type in the schema. Defaults to class
            docstring.
        interfaces (Iterable[graphene.Interface]): GraphQL interfaces to extend with the payload
            object. All fields from interface will be included in this object's schema.
        fields (Dict[str, graphene.Field]): Dictionary of field name to Field. Not recommended to
            use (prefer class attributes or ``Meta.output``).
    """

    @classmethod
    def __init_subclass_with_meta__(
        cls,
        interfaces=(),
        resolver=None,
        output=None,
        arguments=None,
        _meta=None,
        **options
    ):
        if not _meta:
            _meta = MutationOptions(cls)

        output = output or getattr(cls, "Output", None)
        fields = {}

        for interface in interfaces:
            assert issubclass(interface, Interface), (
                'All interfaces of {} must be a subclass of Interface. Received "{}".'
            ).format(cls.__name__, interface)
            fields.update(interface._meta.fields)

        if not output:
            # If output is defined, we don't need to get the fields
            fields = {}
            for base in reversed(cls.__mro__):
                fields.update(yank_fields_from_attrs(base.__dict__, _as=Field))
            output = cls

        if not arguments:
            input_class = getattr(cls, "Arguments", None)
            if not input_class:
                input_class = getattr(cls, "Input", None)
                if input_class:
                    warn_deprecation(
                        (
                            "Please use {name}.Arguments instead of {name}.Input."
                            " Input is now only used in ClientMutationID.\n"
                            "Read more:"
                            " https://github.com/graphql-python/graphene/blob/v2.0.0/UPGRADE-v2.0.md#mutation-input"
                        ).format(name=cls.__name__)
                    )

            if input_class:
                arguments = props(input_class)
            else:
                arguments = {}

        if not resolver:
            mutate = getattr(cls, "mutate", None)
            assert mutate, "All mutations must define a mutate method in it"

            def resolver(*args, **kwargs):
                run_validators(arguments, *args, **kwargs)
                return get_unbound_function(mutate)(*args, **kwargs)

        if _meta.fields:
            _meta.fields.update(fields)
        else:
            _meta.fields = fields

        _meta.interfaces = interfaces
        _meta.output = output
        _meta.resolver = resolver
        _meta.arguments = arguments

        super(Mutation, cls).__init_subclass_with_meta__(_meta=_meta, **options)

    @classmethod
    def Field(
        cls, name=None, description=None, deprecation_reason=None, required=False
    ):
        """ Mount instance of mutation Field. """
        return Field(
            cls._meta.output,
            args=cls._meta.arguments,
            resolver=cls._meta.resolver,
            name=name,
            description=description or cls._meta.description,
            deprecation_reason=deprecation_reason,
            required=required,
        )
