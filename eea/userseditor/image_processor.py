from StringIO import StringIO

from PIL import Image


def scaled_size(im, width, height):
    """
    Given the width and height bounderies, return the new width and height
    of maxium scaled `im` image, maintaining ratio, that fits these bounderies

    """
    (current_w, current_h) = im.size
    boundary_ration = width / float(height)
    im_ratio = current_w / float(current_h)
    if boundary_ration <= im_ratio:
        # width fits perfectly
        new_w = width
        new_h = round(new_w / im_ratio)
    else:
        new_h = height
        new_w = round(im_ratio * new_h)
    return (int(new_w), int(new_h))

def scale_to(filedata, width, height, fill_color):
    """
    Scales image to width X heigth px, maintaining aspect ratio by filling
    with `fill_color`
    Returns JPEG byte data

    """
    imfile = StringIO(filedata)
    im = Image.open(imfile)
    im.load()
    photo_size = scaled_size(im, width, height)
    im = im.resize(photo_size, Image.ANTIALIAS)

    final_im = Image.new("RGB", (width, height), fill_color)
    paste_pos = ((width-photo_size[0])/2, (height-photo_size[1])/2)
    final_im.paste(im, paste_pos)

    new_image = StringIO()
    final_im.save(new_image, "JPEG")
    new_image.seek(0)
    return new_image.read()
