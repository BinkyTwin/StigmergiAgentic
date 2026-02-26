from weasyprint import HTML
import markdown

# Read the README
with open('pdfs/018_CrewAI_README.md', 'r') as f:
    md_content = f.read()

# Convert markdown to HTML
md = markdown.Markdown(extensions=['fenced_code', 'tables', 'toc'])
html_body = md.convert(md_content)

full_html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: -apple-system, sans-serif; line-height: 1.6; margin: 50px; }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; margin-top: 30px; }}
        h3 {{ color: #555; }}
        code {{ background-color: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-family: monospace; }}
        pre {{ background-color: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; }}
        pre code {{ background: none; padding: 0; color: inherit; }}
        a {{ color: #3498db; }}
    </style>
</head>
<body>
{html_body}
</body>
</html>'''

HTML(string=full_html).write_pdf('pdfs/018_CrewAI_Multi-Agent_Platform.pdf')
print('PDF created successfully')
