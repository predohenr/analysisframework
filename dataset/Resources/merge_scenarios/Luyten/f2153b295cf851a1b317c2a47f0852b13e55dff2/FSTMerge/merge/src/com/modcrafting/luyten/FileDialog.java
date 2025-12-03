package com.modcrafting.luyten; 

import java.awt.Component; 
import java.io.File; 
import javax.swing.JFileChooser; 
import javax.swing.filechooser.FileFilter; 

/**
 * FileChoosers for Open and Save
 */
  class  FileDialog {
	
	

	
	

	
	

	
	

	
	

	
	

	

	<<<<<<< /home/ppp/Research_Projects/Merge_Conflicts/Resource/workspace/Luyten/fstmerge_tmp1700674248104/fstmerge_var1_4762542397974154839
=======
public FileDialog(Component parent) {
		this.parent = parent;
		configSaver = ConfigSaver.getLoadedInstance();
		luytenPrefs = configSaver.getLuytenPreferences();

		new Thread() {
			public void run() {
				try {
					initOpenDialog();
					Thread.sleep(500);
					initSaveAllDialog();
					Thread.sleep(500);
					initSaveDialog();
				} catch (Exception e) {
					e.printStackTrace();
				}
			};
		}.start();
	}
>>>>>>> /home/ppp/Research_Projects/Merge_Conflicts/Resource/workspace/Luyten/fstmerge_tmp1700674248104/fstmerge_var2_7742139323251021299


	

	

	

	

	

	<<<<<<< /home/ppp/Research_Projects/Merge_Conflicts/Resource/workspace/Luyten/fstmerge_tmp1700674248281/fstmerge_var1_702703801114255177
=======
public File doSaveAllDialog(String recommendedFileName) {
		File selectedFile = null;
		initSaveAllDialog();

		retrieveSaveDialogDir(fcSaveAll);
		fcSaveAll.setSelectedFile(new File(recommendedFileName));
		int returnVal = fcSaveAll.showSaveDialog(parent);
		saveSaveDialogDir(fcSaveAll);

		if (returnVal == JFileChooser.APPROVE_OPTION) {
			selectedFile = fcSaveAll.getSelectedFile();
		}
		return selectedFile;
	}
>>>>>>> /home/ppp/Research_Projects/Merge_Conflicts/Resource/workspace/Luyten/fstmerge_tmp1700674248281/fstmerge_var2_4891689415124647647


	

	

	

	

	

	

	

	

	

	  class  FileChooserFileFilter  extends FileFilter {
		
		

		

		

		

		

		

		


	}

	

	

	

	

	

	

	

	


}
