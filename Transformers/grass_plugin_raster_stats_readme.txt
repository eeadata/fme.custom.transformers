To make this transformer available in FME Workbench:

# Check (and copy when unavailable) the GRASS platform into the 'FME/install/transformers' directory:

 - grass_plugin_core:     Folder of the GRASS runtime with native applications.
 - grass_plugin_utils.py: Generic GRASS python class manager.

 These resources are common used by transformers that integrate GRASS applications.

# Copy the specific python file (*.py) and the transformer file (*.fmx) into the 'FME/install/transformers' directory:

  - grass_plugin_xxx_yyy.fmx: FME transformer declaration file
  - grass_plugin_xxx_yyy.py:  FME transformer python file

 These resources are specific of each transformer.
