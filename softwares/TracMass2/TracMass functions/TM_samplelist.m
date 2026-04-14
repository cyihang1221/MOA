classdef TM_samplelist < handle
    
    %arguments: parent
    %A class for the samplelist used in the UI of TM_tracker,
    %TM_peakdetection and TM_alignment.
    
    %by: Erik Tengstrand
    
    properties
        Samples        %the names of the samples
        SamplePath     %the full name (including path) of the samples
        CurrentSample  %the sample number when a single sample is selected (its number in obj.Samples)
        MultiSample    %the sample numbers when multiple samples are selected (theirs numbers in obj.Samples)
        ProjectPath    %output path for tracking, peak detection etc.
        ListBox        %a handle
        panel
    end
    
    events
        ChangeSample   %an event for when a new sample is selected
        Change
        Finished
    end
    
        methods
        
            function obj=TM_samplelist(parent,title)
                if nargin==1
                    title='Samples';
                end
                vbox=uiextras.VBox('Parent',double(parent),'Spacing',0,'Padding',0);
                obj.panel=uiextras.Panel('Parent',double(vbox),'Title',title);
                obj.ListBox=uicontrol('Parent',double(obj.panel),'Style','ListBox','String',obj.Samples,'Max',10000,'Callback',@(src,evt)GetSample(obj));
                
            end
            
            
            function GetSample(obj)
                if ischar(obj.Samples)
                    obj.Samples={obj.Samples};
                    obj.SamplePath={obj.SamplePath};
                end
                SampleSelection=get(obj.ListBox,'Value');
                obj.MultiSample=SampleSelection;
                notify(obj,'Change')
                if numel(SampleSelection)==1
                    obj.CurrentSample=SampleSelection;
                    notify(obj,'ChangeSample')
                end
            end
        end
end
