import frappe

from subprocess import PIPE, Popen


def generate_and_attach_og_image(doc, method=None):
    # TODO: DB call can be (and should be) prevented by caching
    # the list of docs for which the template is enabled
    # But for now, eh.

    # If there is a template and is enabled, only then proceed
    if not frappe.db.exists(
        "OG Image Template", {"for_doctype": doc.doctype, "is_enabled": 1}
    ):
        return

    file_name = get_file_name(doc)
    content = get_processed_html_content(doc)
    stdout, stderr = generate_and_get_image_from_node_process(content)

    if not stderr:
        file_doc = create_file_doc(file_name, stdout, doc.doctype, doc.name)
    else:
        # Maybe add a comment to the document?
        # + log an error?
        frappe.throw("Error generating image file")

    try:
        delete_old_images_if_applicable(doc, file_doc.name)
    except Exception:
        doc.log_error(
            "Error Deleting Old OG Images",
            "There was an error while deleting old OG images",
        )


def create_file_doc(name, content, attached_to_doctype, attached_to_name):
    file_doc = frappe.new_doc("File")
    file_doc.file_name = name
    file_doc.content = content
    file_doc.attached_to_doctype = attached_to_doctype
    file_doc.attached_to_name = attached_to_name
    file_doc.save()

    return file_doc


def get_file_name(doc):
    suffix = frappe.generate_hash(length=8)
    doc_info = frappe.scrub(f"{doc.doctype}_{doc.name}")
    return f"og_image_{doc_info}_{suffix}.png"


def get_processed_html_content(doc):
    template_html = frappe.db.get_value(
        "OG Image Template",
        {"for_doctype": doc.doctype, "is_enabled": 1},
        "template_html",
    )
    content = frappe.render_template(template_html, {"doc": doc})
    return content.replace("\n", "")


def generate_and_get_image_from_node_process(html_content):
    command = ["node", "play.js", html_content]

    process = Popen(
        command,
        cwd=frappe.get_app_path("frappe_dynamic_og", "../playground"),
        stdout=PIPE,
        stderr=PIPE,
    )

    return process.communicate()


def delete_old_images_if_applicable(doc, new_file_doc_name):
    to_delete = frappe.db.get_single_value(
        "Frappe Dynamic OG Settings", "automatically_delete_old_images"
    )

    if to_delete:
        doc_info = frappe.scrub(f"{doc.doctype}_{doc.name}")
        old_image_files = frappe.db.get_all(
            "File", {"file_name": ("like", f"og_image_{doc_info}%")}, pluck="name"
        )
        for name in old_image_files:
            if name == new_file_doc_name:
                # this is the newly created file!
                continue
            frappe.delete_doc("File", name)
