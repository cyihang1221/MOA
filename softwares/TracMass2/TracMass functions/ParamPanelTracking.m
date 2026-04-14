classdef ParamPanelTracking < ParamPanel
    
    %by: Erik Tengstrand
    
    properties
        transformation={'sqrt' 'none'}
    end
    
    methods
        function obj=ParamPanelTracking(param,LeftBox)
            obj@ParamPanel(param,'Parent',LeftBox,'Title','Parameters');
            set(obj.hEdit(5),'style','popupmenu','string',obj.transformation,'value',1,'max',numel(obj.transformation),'min',1,'Callback',@(src,evt)obj.popupCallback(src));
        end
        
        function refresh( obj )
            p = obj.param.getEditableAsStruct;
            fn = fieldnames( p );
            for i = 1 : numel( fn )
                if strcmpi(get(obj.hEdit(i),'style'),'popupmenu')
                    set( obj.hEdit( i ), 'value', p.( fn{i} ) )
                else
                    set( obj.hEdit( i ), 'String', num2str( p.( fn{i} ) ) )
                end
            end
        end
        
        function popupCallback(obj,src)
            try
                obj.param.mzTransformation = get( src, 'value' );
            catch me
                set( src, 'value', obj.param.mzTransformation )
                disp(me.message)
            end
            set( src, 'value', obj.param.mzTransformation )
            
        end
    end
end