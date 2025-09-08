{% import 'macros.rst' as macros %}

{% if obj.display %}
{% if is_own_page %}

{{ obj.id }}
{{ "=" * obj.id|length }}

.. currentmodule:: {{ obj.obj["full_name"] }}



{% if obj.docstring %}
.. autoapi-nested-parse::

   {{ obj.docstring|indent(3) }}

{% endif %}

{% block submodules %}
    {% set visible_subpackages = obj.subpackages|selectattr("display")|list %}
    {% set visible_submodules = obj.submodules|selectattr("display")|list %}
    {% set visible_submodules = (visible_subpackages + visible_submodules)|sort %}
    {% if visible_submodules %}
Submodules
----------
.. toctree::
   :titlesonly:
   :maxdepth: 3

    {% for submodule in visible_submodules %}
   {{ submodule.include_path }}
    {% endfor %}


    {% endif %}
{% endblock %}

{% block overview %}
{% set visible_children = obj.children|selectattr("display")|list %}
{% set visible_classes = visible_children|selectattr("type", "equalto", "class")|list %}
{% set visible_exceptions = visible_children|selectattr("type", "equalto", "exception")|list %}
{% set visible_functions = visible_children|selectattr("type", "equalto", "function")|list %}
{% set visible_attributes = visible_children|selectattr("type", "equalto", "data")|list %}
{% if visible_classes or visible_functions or visible_attributes or visible_exceptions %}
Overview
--------
{% endif %}

{% block classes scoped %}
{% if visible_classes %}
{{ macros.auto_summary(visible_classes, title="Classes") }}

{% endif %}
{% endblock %}

{% block functions scoped %}
{% if visible_functions %}
{{ macros.auto_summary(visible_functions, title="Function") }}
{% endif %}
{% endblock %}

{% block attributes scoped %}
{% if visible_attributes %}
{{ macros.auto_summary(visible_attributes, title="Attributes") }}
{% endif %}
{% endblock %}

{% block exceptions scoped %}
{% if visible_exceptions %}
{{ macros.auto_summary(visible_exceptions, title="Exceptions") }}
{% endif %}
{% endblock %}


{% set this_page_children = visible_children|rejectattr("type", "in", own_page_types)|list %}
{% if this_page_children %}

{{ obj.type|title }} Contents
{{ "-" * obj.type|length }}---------

{% for obj_item in this_page_children %}
{{ obj_item.render()|indent(0) }}
{% endfor %}


{% endif %}

{% endblock %}


{% endif %}
{% endif %}
