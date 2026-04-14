classdef ParamPanel < handle
    %PARAMPANEL Summary of this class goes here
    %   Detailed explanation goes here
    
    %by: Magnus Åberg
    
    properties
        param
        hBoxPanel
        parbox
        hText
        hEdit
        names
    end
    
    methods
        
        function obj = ParamPanel( param, varargin )
            
            p = param.getEditableAsStruct;
            obj.names = fieldnames(p);
            
            obj.hBoxPanel = uiextras.BoxPanel( varargin{:} );
            set( obj.hBoxPanel , 'TitleColor', get(obj.hBoxPanel , 'ShadowColor' ) )
            set( obj.hBoxPanel , 'ForegroundColor', [1 1 1], 'FontWeight', 'bold' )
            
            obj.parbox = uiextras.Grid( 'Parent', obj.hBoxPanel, 'Spacing', ...
                5, 'Padding', 3 );
            
            obj.param = param; % handle of class PeakDetectionZAF2Param
            
            % label column
            for i = 1 : numel( obj.names )
                obj.hText( i ) = uicontrol( 'Style', 'text', 'String', obj.names{i}, ...
                    'Parent', double( obj.parbox ), 'HorizontalAlignment', 'right');
            end
            textWidth = get( obj.hText, 'Extent' );
            if iscell( textWidth )
                textWidth = [ textWidth{:} ];
            end
            textWidth = max( textWidth( 3:4:end ) );
            
            hTextEmpty = uiextras.Empty( 'Parent', obj.parbox );
            
            % edit colum
            for i = 1 : numel( obj.names )
                obj.hEdit( i ) = uicontrol( 'Style', 'edit', 'String', ...
                    num2str( param.( obj.names{i} ) ), 'Parent', double( obj.parbox ), ...
                    'Callback', @( h_, evt_ ) parCallback( obj, h_, obj.names{i} ) );
            end
            hEditEmpty = uiextras.Empty( 'Parent', obj.parbox );
            
            set(obj.parbox, 'ColumnSizes', [textWidth, -1], ...
                'RowSizes', [ repmat( 20, 1, numel( obj.names ) ), -1 ] )
        end
        
        function p = get.param( obj )
            p = obj.param;
        end
        
        function refresh( obj )
            p = obj.param.getEditableAsStruct;
            fn = fieldnames( p );
            for i = 1 : numel( fn )
                set( obj.hEdit( i ), 'String', num2str( p.( fn{i} ) ) )
            end
        end
        
        function parCallback( obj, h, name )
            %disp( name )
            try
                obj.param.(name) = get( h, 'String' );
            catch me
                set( h, 'String', num2str( obj.param.( name ) ) )
                disp(me.message)
            end
            set( h, 'String', num2str( obj.param.( name ) ) )
            
        end
        
    end
end

