import json
from lxml import etree
import numpy as np
import os
from pathlib import Path
from PIL import Image
from PIL.PngImagePlugin import PngInfo

import folder_paths


class JHSaveImageWithXMPMetadata:
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"
        self.prefix_append = ""
        self.compress_level = 0

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "The images to save."}),
                "filename_prefix": ("STRING", {"default": "ComfyUI", "tooltip": "The prefix for the file to save. This may include formatting information such as %date:yyyy-MM-dd% or %Empty Latent Image.width% to include values from nodes."}),
            },
            "optional": {
                "title": ("STRING",),
                "positive_prompt": ("STRING",),
                "negative_prompt": ("STRING",),
                "description": ("STRING",),
                "keywords": ("STRING",),
                "model_path": ("STRING",),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "save_images"
    CATEGORY = "JHXMP"
    OUTPUT_NODE = True

    def save_images(self, images, filename_prefix="ComfyUI",
                    title=None,
                    positive_prompt=None,
                    negative_prompt=None,
                    description=None,
                    keywords=None,
                    model_path=None,
                    prompt=None, extra_pnginfo=None):
        filename_prefix += self.prefix_append
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(filename_prefix, self.output_dir, images[0].shape[1], images[0].shape[0])
        results = list()

        for (batch_number, image) in enumerate(images):
            i = 255. * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))

            metadata = PngInfo()

            # https://developer.adobe.com/xmp/docs/XMPSpecifications/

            namespaces = {
                "x": "adobe:ns:meta/",
                "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                "dc": "http://purl.org/dc/elements/1.1/",
                "xml": "http://www.w3.org/XML/1998/namespace",
                "xmp": "http://ns.adobe.com/xap/1.0/",
            }

            # Create the root x:xmpmeta element
            xmpmeta = etree.Element("{adobe:ns:meta/}xmpmeta", nsmap=namespaces)

            # Set the x:xmptk attribute using the namespace URI
            xmpmeta.set("{adobe:ns:meta/}xmptk", "Adobe XMP Core 6.0-c002 79.164861, 2016/09/14-01:09:01")

            # Create the rdf:RDF container
            rdf = etree.SubElement(xmpmeta, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF")

            # Add the rdf:Description element
            rdf_description = etree.SubElement(
                rdf,
                "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description",
                attrib={"{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about": ""}
            )

            # dc:title
            if title:
                dc_title = etree.SubElement(rdf_description, "{http://purl.org/dc/elements/1.1/}title")
                alt = etree.SubElement(dc_title, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Alt")
                li = etree.SubElement(alt, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li",
                                    attrib={"{http://www.w3.org/XML/1998/namespace}lang": "x-default"})
                li.text = title

            # dc:description
            description_list = []
            if positive_prompt:
                description_list.append(f"Prompt: {positive_prompt}")
            if negative_prompt:
                description_list.append(f"Negative prompt: {negative_prompt}")
            if description:
                description_list.append(f"Description: {description}")
            description_string = "\n\n".join(description_list)
            if description_string:
                dc_description = etree.SubElement(rdf_description, "{http://purl.org/dc/elements/1.1/}description")
                alt = etree.SubElement(dc_description, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Alt")
                li = etree.SubElement(alt, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li",
                                    attrib={"{http://www.w3.org/XML/1998/namespace}lang": "x-default"})
                li.text = description_string

            # dc:creator
            if model_path:
                dc_creator = etree.SubElement(rdf_description, "{http://purl.org/dc/elements/1.1/}creator")
                seq = etree.SubElement(dc_creator, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Seq")
                li = etree.SubElement(seq, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li",
                                    attrib={"{http://www.w3.org/XML/1998/namespace}lang": "x-default"})
                li.text = Path(model_path).stem

            # dc:subject
            keywords_list = []
            if keywords:
                keywords_list = keywords.split(", ")
            dc_subject = etree.SubElement(rdf_description, "{http://purl.org/dc/elements/1.1/}subject")
            seq = etree.SubElement(dc_subject, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Seq")
            for keyword in keywords_list:
                li = etree.SubElement(seq, "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li",
                                    attrib={"{http://www.w3.org/XML/1998/namespace}lang": "x-default"})
                li.text = keyword

            # Convert the ElementTree to a string
            xmp_string = etree.tostring(xmpmeta, pretty_print=False, encoding="UTF-8").decode("utf-8")
            
            # Wrap it in xpacket tags; "\uFEFF" and "W5M0MpCehiHzreSzNTczkc9d" are magic numbers.
            xpacket_wrapped = f"""<?xpacket begin="\uFEFF" id="W5M0MpCehiHzreSzNTczkc9d"?>
            {xmp_string}
            <?xpacket end="w"?>"""

            # Add the metadata to the image
            metadata.add_text("XML:com.adobe.xmp", xpacket_wrapped)

            # Add other metadata (this comes straight from SaveImage)
            if prompt is not None:
                metadata.add_text("prompt", json.dumps(prompt))
            if extra_pnginfo is not None:
                for x in extra_pnginfo:
                    metadata.add_text(x, json.dumps(extra_pnginfo[x]))

            filename_with_batch_num = filename.replace("%batch_num%", str(batch_number))
            file = f"{filename_with_batch_num}_{counter:05}_.png"
            img.save(os.path.join(full_output_folder, file), pnginfo=metadata, compress_level=self.compress_level)
            results.append({
                "filename": file,
                "subfolder": subfolder,
                "type": self.type
            })
            counter += 1

        return { "result": images, "ui": { "images": results } }
