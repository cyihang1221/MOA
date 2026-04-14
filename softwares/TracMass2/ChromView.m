classdef ChromView
    
    %by: Erik Tengstrand
    
    properties
        ChromViewHandle
    end
    
    methods
        function obj=ChromView
            figureHandle=figure('MenuBar','none','Toolbar','figure','Name','Chromatogram Viewer','Numbertitle','off');
            obj.ChromViewHandle=TM_ChromView(figureHandle);
            P=get(figureHandle,'Position');
            set(figureHandle,'Position',[P(1)-100 P(2)-100 P(3)+200 P(4)+100]);
            addlistener(obj.ChromViewHandle,'ProjectUpdate',@(source,evt)obj.Update());
        end
        
        function Update(obj)
            if numel(obj.ChromViewHandle.SampleList.Samples)==0
                files=dir(fullfile(obj.ChromViewHandle.SampleList.ProjectPath, 'raw'));
                for N=1:numel(files)
                    [~,name,ext]=fileparts(files(N).name);
                    ext=lower(ext);
                    if strcmp(ext,'.cdf') || strcmp(ext,'.mzxml') || strcmp(ext,'.mzdata') || strcmp(ext,'.xml') ||  strcmp(ext,'.mzml') || strcmp(ext,'.man') 
                        obj.ChromViewHandle.SampleList.Samples{end+1}=name;
                        obj.ChromViewHandle.SampleList.SamplePath{end+1}=fullfile(obj.ChromViewHandle.SampleList.ProjectPath, 'raw', [name ext]);
                    end
                end
                set(obj.ChromViewHandle.SampleList.ListBox,'String',obj.ChromViewHandle.SampleList.Samples)
                obj.ChromViewHandle.BPC=[];
                obj.ChromViewHandle.TIC=[];
            end
        end
    end
end