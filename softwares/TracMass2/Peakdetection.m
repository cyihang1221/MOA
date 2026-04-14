classdef Peakdetection
    
    %by: Erik Tengstrand
    
    properties
        PeakdetectionHandle
    end
    
    methods
        
        function obj=Peakdetection
            
            figureHandle=figure('MenuBar','none','Toolbar','figure','Name','Peak Detection','Numbertitle','off');
            obj.PeakdetectionHandle=TM_peakdetection(figureHandle);
            P=get(figureHandle,'Position');
            set(figureHandle,'Position',[P(1)-100 P(2)-100 P(3)+200 P(4)+100]);
            addlistener(obj.PeakdetectionHandle,'ProjectUpdate',@(source,evt)obj.Update());
            
        end
        
        function Update(obj)
            files=dir(fullfile(obj.PeakdetectionHandle.SampleList.ProjectPath, 'pic', '*.pic'));
            for N=1:numel(files)
                picfile=fullfile(obj.PeakdetectionHandle.SampleList.ProjectPath, 'pic', files(N).name);
                [~,name,~]=fileparts(picfile);
                obj.PeakdetectionHandle.SampleList.Samples{N}=name;
                obj.PeakdetectionHandle.SampleList.SamplePath{N}=picfile;
            end
            set(obj.PeakdetectionHandle.SampleList.ListBox,'String',obj.PeakdetectionHandle.SampleList.Samples)
            
            %TM_peakdetection checks the scantime(dt) on the first sample
            %that is loaded. This resets the scantime so that it will be
            %checked again if a new project is opened.
            obj.PeakdetectionHandle.Parameters.param.dt=[];
        end
    end
end