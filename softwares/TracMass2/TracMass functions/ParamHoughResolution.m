classdef ParamHoughResolution < handle
    % ParamHoughResolution - A class for holding paramters in GUI apps
    %   Takes care of various...
    
    %by: Magnus Åberg and Erik Tengstrand
    properties
        Components = 2
        TimeTolerance = 1
        Penalty = 1
    end
    
    events
        ParamChange
    end
    
    methods
        function obj = ParamHoughResolution( a )
            if nargin == 0,
                return
            end
            
            if isa( a, 'ParamHoughResolution') || isa( a, 'struct' )
                setAll( obj, a );
                return
            end
        end
        
        function setAll( obj, a )
            fn = fieldnames( obj );
            fn = fn(1:5);
            
            % a can have more fields than obj but must have all that obj
            % has.
            assert( isempty( setdiff( fn, fieldnames( a ) ) ) )
            
            for i = 1 : numel( fn )
                obj.( fn{ i } ) = a.( fn{ i } );
            end
            notify( obj, 'ParamChange' )
        end
        
        function set.Components( obj, val )
            val = validateValueAsPosScalar( val );
            obj.Components = val;
            notify( obj, 'ParamChange' )
        end
        
        function set.TimeTolerance( obj, val )
            val = validateValueAsPosScalar( val );
            obj.TimeTolerance = val;
            notify( obj, 'ParamChange' )
        end
        
        function set.Penalty( obj, val )
            val = validateValueAsPosScalar( val );
            obj.Penalty = val;
            notify( obj, 'ParamChange' )
        end
        
        function s = getEditableAsStruct( obj )
            s.Components=obj.Components;
            s.TimeTolerance=obj.TimeTolerance;
            s.Penalty=obj.Penalty;
        end
        
        function s = getAsStruct( obj )
            warning( 'off', 'MATLAB:structOnObject' )
            s = struct( obj );
            warning( 'on', 'MATLAB:structOnObject' )
        end
        
    end
    
end

