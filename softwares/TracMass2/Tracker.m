classdef Tracker
    
    %by: Erik Tengstrand
    
    properties
        TrackerHandle
    end
    
    methods
        
        function obj=Tracker
            
            figureHandle=figure('MenuBar','none','Toolbar','figure','Name','Tracker','Numbertitle','off');
            obj.TrackerHandle=TM_tracker(figureHandle);
            P=get(figureHandle,'Position');
            set(figureHandle,'Position',[P(1)-100 P(2)-100 P(3)+200 P(4)+100]);
            addlistener(obj.TrackerHandle,'ProjectUpdate',@(source,evt)obj.Update());
            
        end
        
        function Update(obj)
            if numel(obj.TrackerHandle.SampleList.Samples)==0
                files=dir(fullfile(obj.TrackerHandle.SampleList.ProjectPath, 'raw'));
                for N=1:numel(files)
                    [~,name,ext]=fileparts(files(N).name);
                    ext=lower(ext);
                    if strcmp(ext,'.cdf') || strcmp(ext,'.mzxml') || strcmp(ext,'.mzdata') || strcmp(ext,'.xml') ||  strcmp(ext,'.mzml') || strcmp(ext,'.man') 
                        obj.TrackerHandle.SampleList.Samples{end+1}=name;
                        obj.TrackerHandle.SampleList.SamplePath{end+1}=fullfile(obj.TrackerHandle.SampleList.ProjectPath, 'raw',[name ext]);
                    end
                end
                set(obj.TrackerHandle.SampleList.ListBox,'String',obj.TrackerHandle.SampleList.Samples)
            end
        end
    end
end