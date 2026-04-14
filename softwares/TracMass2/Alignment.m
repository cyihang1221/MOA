classdef Alignment
    
    %by: Erik Tengstrand
    
    properties
        AlignmentHandle
    end
    
    methods
        
        function obj=Alignment
            
            figureHandle=figure('MenuBar','none','Toolbar','figure','Name','Alignment','Numbertitle','off');
            obj.AlignmentHandle=TM_alignment(figureHandle);
            P=get(figureHandle,'Position');
            set(figureHandle,'Position',[P(1)-100 P(2)-100 P(3)+200 P(4)+100]);
            addlistener(obj.AlignmentHandle,'ProjectUpdate',@(source,evt)obj.Update());
            
        end
        
        function Update(obj)
            if numel(obj.AlignmentHandle.SampleList.Samples)==0
                files=dir(fullfile(obj.AlignmentHandle.SampleList.ProjectPath, 'peak', '*.peak'));
                for N=1:numel(files)
                    peakfile=fullfile(obj.AlignmentHandle.SampleList.ProjectPath, 'peak', files(N).name);
                    [~,name,ext]=fileparts(peakfile);
                    obj.AlignmentHandle.SampleList.Samples{N}=name;
                    obj.AlignmentHandle.SampleList.SamplePath{N}=peakfile;
                end
                set(obj.AlignmentHandle.SampleList.ListBox,'String',obj.AlignmentHandle.SampleList.Samples)
            end
        end
    end
end