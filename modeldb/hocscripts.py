driver_hoc_header = r"""
strdef verify_dir_ 
verify_dir_ = "{model_dir}"
"""

driver_hoc_body = r"""
if (name_declared("verify_dir_") == 0) {
	execute("~strdef verify_dir_")
	execute("verify_dir_ = \".\"")
}
strdef verify_tstr_
objref verify_glist_, verify_xvec_, verify_yvec_, verify_file_
verify_file_ = new File()
sprint(verify_tstr_, "%s/gout", verify_dir_)
verify_file_.wopen(verify_tstr_)
verify_xvec_ = new Vector()
verify_yvec_ = new Vector()
verify_glist_ = new List("Graph")

proc verify_graph_() {local i, j, k
	verify_file_.printf("Graphs %d\n", verify_glist_.count)
	for i=0, verify_glist_.count-1 {
		verify_file_.printf("%s\n", verify_glist_.object(i))
		k = 0
		for (j=-1; (j=verify_glist_.object(i).line_info(j, verify_xvec_)) != -1; ){
			k += 1
		}
		verify_file_.printf("lines %d\n", k)
		for (j=-1; (j=verify_glist_.object(i).getline(j, verify_xvec_, verify_yvec_)) != -1; ){
			verify_file_.printf("points %d\n", verify_xvec_.size)
			verify_file_.printf("xvec%d\n", j)
			verify_xvec_.printf(verify_file_)
			verify_file_.printf("yvec%d\n", j)
			verify_yvec_.printf(verify_file_)
		}
	}
}
"""

quit_hoc = r"""
quit()
"""
