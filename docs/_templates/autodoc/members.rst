{% if members %}
{% for member in members %}
{{ member.name | underline(2) }}

.. automethod:: {{ member.fullname }}
   :noindex:

   {% if member.docstring %}
   {{ member.docstring | indent(3) }}
   {% else %}
   *No docstring available.*
   {% endif %}

{% endfor %}
{% endif %}