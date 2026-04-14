classdef ParamPSplineWarping < handle
    %ParamPSplineWarping - A class for holding paramters in GUI apps
    %   Takes care of various...
    
    %by: Magnus Åberg
    
    properties ( SetAccess = public )
        numPSplines = 1;
        lambda      = 1;
        PSplineChanged = 0;
    end
    
    properties ( SetAccess = private )
    end
    
    properties ( Constant = true )
    end
    
    events
        ParamChange
    end
    
    methods
        function obj = ParamPSplineWarping( a )
            if nargin == 0,
                return
            end
            
            if isa( a, 'ParamPSplineWarping') || isa( a, 'struct' )
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
        
        function set.numPSplines( obj, val )
            val = validateValueAsPosScalar( val );
            assert( mod( val, 1 ) == 0, 'Value of numPSplines must be an integer.' )
            obj.numPSplines = val;
            obj.PSplineChanged = 1;
            notify( obj, 'ParamChange' )
        end
        
        function set.lambda( obj, val )
            val = validateValueAsPosScalar( val );
            obj.lambda = val;
            notify( obj, 'ParamChange' )
        end
        

    
        function s = getEditableAsStruct( obj )
            s.numPSplines = obj.numPSplines;
            %the new warping method selects lambda automatically.
            %s.lambda      = obj.lambda;
        end
        
        function s = getAsStruct( obj )
            warning( 'off', 'MATLAB:structOnObject' )
            s = struct( obj );
            warning( 'on', 'MATLAB:structOnObject' )
        end
    end
end
