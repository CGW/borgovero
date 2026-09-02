"""The sepia tint, in ONE place. (S010)

Two pipelines apply this — `make_comune_images.py` for our own photographs
of the eight comuni, `harvest_listing_images.py` for the agencies' listing
photographs — and they must produce the same palette or the two kinds of
image sit side by side on a page looking like a mistake. A constant copied
into two files is a constant that diverges; S009 spent a paragraph on
`photomatch.DELAY_S` for the same reason.

WHAT S009 DECIDED, WHAT S010 CHANGED, AND WHAT DID NOT CHANGE

S009 considered sepia for listing photographs and rejected it, on the
argument that a tint is not a transformation, it changes nothing about
copyright or personal data, and it reads as disguise rather than good
faith. Christopher reversed that in S010 and asked for sepia everywhere.

The reversal is a VISUAL decision and it is his to make. What matters is
that it does not quietly become a legal one. Nothing in S009's actual
protections moves: the photographs are still credited in 8pt with a link,
still EXIF-stripped, still capped at 600px, still consulted against the
opt-out at fetch AND at render, still removed on request. Sepia is applied
ON TOP of all of that, not instead of any of it.

So the honest description of the tint is that it makes the site look like
one site. It is not a claim about ownership, it does not make a photograph
ours, and it must never be described — here or on the site — as anything
that reduces exposure. If it ever starts being cited as a mitigation, that
is the moment this comment has failed.

WHY A GREYSCALE RAMP RATHER THAN A MATRIX ON RGB

Multiplying RGB by the classic sepia matrix leaves some of the original
hue behind, so a green valley and a terracotta roof come out at different
temperatures and eight photographs stop looking like a set. Going through
luminance first throws the original colour away completely and maps every
input onto the same ramp. That is the whole point on a page where the
images come from ten different cameras and ten different agencies.
"""

# The classic sepia coefficients, per output channel.
_COEF = ((0.393, 0.769, 0.189),
         (0.349, 0.686, 0.168),
         (0.272, 0.534, 0.131))

# Precomputed 0-255 ramps, one per output channel.
_RAMP = [[min(255, int(i * sum(c))) for i in range(256)] for c in _COEF]


def sepia(im):
    """RGB image -> sepia-toned RGB image.

    Stable under repetition: re-toning an already-toned image lands on
    essentially the same pixels, because the ramp is driven by luminance
    and toning barely moves it. That matters because `--resepia` can be
    run twice by accident and must not compound into brown mud.
    """
    from PIL import Image
    g = im.convert("L")
    return Image.merge("RGB", [g.point(_RAMP[b]) for b in range(3)])
