<!-- Test Coverage: 438e0fc3-cf8d-4282-8856-c3e3b6a06a2f -->
{% for section in sections %}
<details>
    <summary>
        <h3 style="margin: 0;">{{ section.name }}</h3>
    </summary>
    <div>{{ section.content }}</div>
</details>
{% endfor %}
