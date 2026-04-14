classdef TM_ui < handle
    
    %creates the three buttons 'set project directory', 'save parameters'
    %and 'load parameters', and contains their callback functions.
    
    %by: Erik Tengstrand
    
    properties
        ext
    end
    
    events
        ProjectUpdate
    end
    
    methods
        
        function obj=TM_ui(parentobj,parent,type)
            
            uicontrol('Parent',double(parent),'Style','PushButton','String','Set Project Folder','Callback',@(src,evt)obj.SetProjectDir(parentobj));
            obj.ext=['.' type 'param'];
            
            %different functions as TM_alignment has separate parameters
            %for the database and the alignment methods
            if strcmp(type,'alignment')
                uicontrol('Parent',double(parent),'Style','PushButton','String','Save Parameters','Callback',@(src,evt)obj.SaveAlignmentParameters(parentobj));
                uicontrol('Parent',double(parent),'Style','PushButton','String','Load Parameters','Callback',@(src,evt)obj.LoadAlignmentParameters(parentobj,type));
            else
                uicontrol('Parent',double(parent),'Style','PushButton','String','Save Parameters','Callback',@(src,evt)obj.SaveParameters(parentobj));
                uicontrol('Parent',double(parent),'Style','PushButton','String','Load Parameters','Callback',@(src,evt)obj.LoadParameters(parentobj,type));
            end
        end
            
        function SetProjectDir(~,parentobj)
            pdir=uigetdir([],'Select a project folder');
            if ischar(pdir)
                parentobj.SampleList.ProjectPath=pdir;
                notify(parentobj,'ProjectUpdate')
            end
        end
        
        function SaveParameters(obj,parentobj)
            
            [filename pathname]=uiputfile(obj.ext,'',parentobj.SampleList.ProjectPath);
            if ischar(filename)
                savefile=fullfile(pathname,filename);
                param=parentobj.Parameters.param;
                if ischar(savefile)
                    save(savefile,'param','-mat');
                end
            end
        end
        
        function LoadParameters(obj,parentobj,type)
            
            [filename pathname]=uigetfile(obj.ext,'',parentobj.SampleList.ProjectPath);
            if ischar(filename)
                loadfile=fullfile(pathname,filename);
                loadparam=load(loadfile,'-mat','param');
                try
                    parentobj.Parameters.param=loadparam.param;
                    parentobj.Parameters.refresh
                    notify(parentobj,'Update')
                catch
                    errordlg( sprintf('The file is an invalid %s parameter file',type),'Loading error');
                end
            end
        end
        
        function SaveAlignmentParameters(obj,parentobj)
            
            [filename pathname]=uiputfile(obj.ext,'',parentobj.SampleList.ProjectPath);
            if ischar(filename)
                savefile=fullfile(pathname,filename);
                Param.db=parentobj.Parameters.param;
                Param.c1=parentobj.Cluster1.parameters.param;
                Param.W=parentobj.Warp.parameters.param;
                Param.c2=parentobj.Cluster2.parameters.param;
                Param.H=parentobj.GFHT.parameters.param;
                if ischar(savefile)
                    save(savefile,'Param','-mat');
                end
            end
        end
        
        function LoadAlignmentParameters(obj,parentobj,type)
            
            [filename pathname]=uigetfile(obj.ext,'',parentobj.SampleList.ProjectPath);
            if ischar(filename)
                loadfile=fullfile(pathname,filename);
                Param=load(loadfile,'-mat');
                try
                    parentobj.Parameters.param=Param.Param.db;
                    parentobj.Cluster1.parameters.param=Param.Param.c1;
                    parentobj.Cluster1.parameters.refresh;
                    parentobj.Warp.parameters.param=Param.Param.W;
                    parentobj.Warp.parameters.refresh;
                    parentobj.Cluster2.parameters.param=Param.Param.c2;
                    parentobj.Cluster2.parameters.refresh;
                    parentobj.GFHT.parameters.param=Param.Param.H;
                    parentobj.GFHT.parameters.refresh;
                catch
                    errordlg( sprintf('The file is an invalid %s parameter file',type),'Loading error');
                end
            end
        end
    end
end
