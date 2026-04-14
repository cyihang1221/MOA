classdef ParamDelaunayClustering < handle
    %ParamDelaunayClustering - A class for holding paramters in GUI apps
    %   Takes care of various...
    
    %by: Magnus Åberg and Erik Tengstrand
    properties ( SetAccess = public )
        deltaTime
        deltaMass
        DTChanged=0;
    end
    
    properties ( SetAccess = private )
    end
    
    properties ( Constant = true )
    end
    
    events
        ParamChange
    end
    
    methods
        function obj = ParamDelaunayClustering( a )
            obj.deltaTime = 1;
            obj.deltaMass = 1;
            
            if nargin == 0,
                return
            end
            
            if isa( a, 'PeakDetectionZAF2Param') || isa( a, 'struct' )
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
        
        function set.deltaTime( obj, val )
            val = validateValueAsPosScalar( val );
            obj.deltaTime = val;
            obj.DTChanged=1;
            notify( obj, 'ParamChange' )
        end
        
        function set.deltaMass( obj, val )
            val = validateValueAsPosScalar( val );
            obj.deltaMass = val;
            notify( obj, 'ParamChange' )
        end
    
        function s = getEditableAsStruct( obj )
            s.deltaTime = obj.deltaTime;
            s.deltaMass = obj.deltaMass;
        end
        
        function s = getAsStruct( obj )
            warning( 'off', 'MATLAB:structOnObject' )
            s = struct( obj );
            warning( 'on', 'MATLAB:structOnObject' )
        end
    end
end
