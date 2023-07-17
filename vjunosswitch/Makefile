VENDOR=Juniper
NAME=vjunos-switch
IMAGE_FORMAT=qcow
IMAGE_GLOB=*.qcow2

# match versions like:
# vjunos-switch-23.1R1.8.qcow2
# vjunos-switch-22.1R2.2.qcow2
# vjunos-switch-21.2R4.3.qcow2
# ...

#VERSION=$(shell echo $(IMAGE) | sed -e 's/.\+[^0-9]\([0-9][0-9]\.[0-9][A-Z][0-9]\+\(\.[0-9]\+\|-[SD][0-9]\+\(\.[0-9]\+\)\?\)\)[^0-9].*$$/\1/')
VERSION=$(shell echo $(IMAGE) | sed -e 's/vjunos-switch-//' | sed -e 's/.qcow2//')

-include ../makefile-sanity.include
-include ../makefile.include
